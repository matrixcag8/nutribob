package com.roberto.grillo

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.SamplerConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Il grillo parlante: commenta ogni voce del diario con Qwen3 1.7B che gira sul telefono. */
object Grillo {
    private val hm = DateTimeFormatter.ofPattern("HH:mm")
    private val dayFmt = DateTimeFormatter.ofPattern("d MMM yyyy", Locale.ITALIAN)

    fun instructions(tone: Tone): String {
        val voice = when (tone) {
            Tone.gentile -> "Tono gentile e incoraggiante, mai giudicante."
            Tone.diretto -> "Tono diretto e franco, senza giri di parole, ma mai offensivo."
        }
        return "Sei il Grillo Parlante, la coscienza alimentare dell'utente. Rispondi sempre in italiano. " +
            "Non dai ordini né diete: lo fai ragionare sulle sue scelte rispetto al suo obiettivo. " +
            "Dopo ogni alimento segnato scrivi un commento di massimo due frasi, possibilmente chiuso " +
            "da una domanda che faccia riflettere. Usa solo i numeri forniti, non fare calcoli e non " +
            "inventare numeri. Non dare consigli medici. $voice"
    }

    fun prompt(entry: Entry, history: List<Entry>, profile: Profile): String {
        val today = history.filter { it.day == entry.day }
        val list = today.map { "- ${it.date.format(hm)} ${it.name} ${it.grams.g}, ${it.kcal.toInt()} kcal" }
        val week = history.filter { it.date > entry.date.minusDays(7) }.groupBy { it.day }.toSortedMap()
            .map { (day, items) -> "- ${day.format(dayFmt)}: ${items.sumOf { it.kcal }.toInt()} kcal" }
        val kcalToday = today.sumOf { it.kcal }
        val proteinToday = today.sumOf { it.protein ?: 0.0 }
        // i conti li facciamo qui: un modello piccolo sbaglia l'aritmetica
        return """
            |Obiettivo dell'utente: ${profile.goal.name} di peso. Target giornaliero: ${profile.target.toInt()} kcal, proteine ${profile.protein.toInt()} g.
            |Ha appena segnato alle ${entry.date.format(hm)}: ${entry.name}, ${entry.grams.g}, ${entry.kcal.toInt()} kcal, proteine ${entry.protein.g}, carboidrati ${entry.carbs.g}, grassi ${entry.fat.g}.
            |Oggi finora: ${kcalToday.toInt()} kcal (mancano ${(profile.target - kcalToday).toInt()} al target), proteine ${proteinToday.toInt()} g (mancano ${(profile.protein - proteinToday).toInt()}).
            |${list.joinToString("\n")}
            |Calorie degli ultimi 7 giorni:
            |${week.joinToString("\n")}
        """.trimMargin()
    }

    suspend fun comment(ctx: Context, entry: Entry, history: List<Entry>, tone: Tone, profile: Profile): String? {
        val engine = LocalModel.engine(ctx) ?: return null
        return withContext(Dispatchers.Default) {
            runCatching {
                val config = ConversationConfig(
                    systemInstruction = Contents.of(instructions(tone)),
                    samplerConfig = SamplerConfig(topK = 40, topP = 0.95, temperature = 0.7),
                    maxOutputToken = 200,
                )
                engine.createConversation(config).use {
                    stripThinking(it.sendMessage(prompt(entry, history, profile), mapOf("enable_thinking" to false)).toString())
                }
            }.getOrNull()?.ifBlank { null }
        }
    }

    /** Qwen3 può lasciare un blocco <think></think> vuoto anche col ragionamento spento. */
    fun stripThinking(text: String) = text.replace(Regex("<think>[\\s\\S]*?</think>"), "").trim()
}

/** Qwen3 1.7B int4 (~1 GB): si scarica una volta da Hugging Face, poi gira offline. */
object LocalModel {
    private const val URL =
        "https://huggingface.co/litert-community/Qwen3-1.7B/resolve/main/Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm"

    var progress by mutableStateOf<Float?>(null); private set  // non null durante il download
    var error by mutableStateOf<String?>(null); private set
    var downloaded by mutableStateOf(false); private set
    private var engine: Engine? = null
    private val lock = Mutex()

    private fun file(ctx: Context) = File(ctx.getExternalFilesDir(null), "qwen3-1.7b.litertlm")
    fun refresh(ctx: Context) { downloaded = file(ctx).exists() }

    /** Carica il modello solo se è già scaricato. La prima volta impiega qualche secondo. */
    suspend fun engine(ctx: Context): Engine? = lock.withLock {
        if (engine == null && file(ctx).exists()) withContext(Dispatchers.Default) {
            engine = runCatching {
                // shortcut: solo CPU, la GPU Adreno 630 del 6T via OpenCL non è testata; provare Backend.GPU() se è troppo lento
                Engine(EngineConfig(file(ctx).path, Backend.CPU(), maxNumTokens = 1536, cacheDir = ctx.cacheDir.path))
                    .apply { initialize() }
            }.onFailure { error = "Il modello non si carica: ${it.message}" }.getOrNull()
        }
        engine
    }

    /** Scarica col DownloadManager di sistema: continua anche se l'app va in background. */
    suspend fun download(ctx: Context) {
        if (progress != null) return
        val dm = ctx.getSystemService(DownloadManager::class.java)
        val prefs = ctx.getSharedPreferences("grillo", Context.MODE_PRIVATE)
        var id = prefs.getLong("downloadId", -1)
        if (id < 0 || status(dm, id) == null) {
            val part = File(file(ctx).path + ".part").apply { delete() }
            id = dm.enqueue(DownloadManager.Request(Uri.parse(URL))
                .setTitle("Cervello del grillo")
                .setDestinationUri(Uri.fromFile(part)))
            prefs.edit().putLong("downloadId", id).apply()
        }
        error = null
        progress = 0f
        while (true) {
            val (st, p) = status(dm, id) ?: (DownloadManager.STATUS_FAILED to 0f)
            progress = p
            if (st == DownloadManager.STATUS_SUCCESSFUL) {
                File(file(ctx).path + ".part").renameTo(file(ctx))
                break
            }
            if (st == DownloadManager.STATUS_FAILED) {
                error = "Download fallito, riprova."
                break
            }
            delay(500)
        }
        prefs.edit().remove("downloadId").apply()
        progress = null
        refresh(ctx)
    }

    /** Riprende a mostrare il progresso se un download era in corso alla chiusura dell'app. */
    suspend fun resume(ctx: Context) {
        if (ctx.getSharedPreferences("grillo", Context.MODE_PRIVATE).getLong("downloadId", -1) >= 0) download(ctx)
    }

    private fun status(dm: DownloadManager, id: Long): Pair<Int, Float>? =
        dm.query(DownloadManager.Query().setFilterById(id)).use { c ->
            if (!c.moveToFirst()) return null
            val done = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
            val total = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
            c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)) to if (total > 0) done.toFloat() / total else 0f
        }
}
