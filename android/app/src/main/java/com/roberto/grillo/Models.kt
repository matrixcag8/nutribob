package com.roberto.grillo

import android.content.Context
import android.content.SharedPreferences
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.time.LocalDate
import java.time.LocalDateTime
import java.util.UUID
import kotlin.math.max
import kotlin.math.roundToInt

/** Alimento del database (valori per 100 g). Macro null = non ancora noti. */
data class Food(
    val name: String, val kcal: Double, val protein: Double?, val carbs: Double?, val fat: Double?,
    val portion: Double, val portionLabel: String,
) {
    companion object {
        fun parse(json: String): List<Food> {
            val arr = JSONArray(json)
            fun JSONObject.num(k: String) = if (isNull(k)) null else getDouble(k)
            return (0 until arr.length()).map { i ->
                with(arr.getJSONObject(i)) {
                    Food(getString("name"), getDouble("kcal"), num("protein"), num("carbs"), num("fat"),
                        getDouble("portion"), getString("portionLabel"))
                }
            }
        }
    }
}

/** Voce del diario: i valori sono copiati al momento dell'inserimento. */
data class Entry(
    val date: LocalDateTime, val name: String, val grams: Double, val kcal: Double,
    val protein: Double?, val carbs: Double?, val fat: Double?,
    val comment: String? = null, val id: String = UUID.randomUUID().toString(),
) {
    val day: LocalDate get() = date.toLocalDate()

    constructor(food: Food, grams: Double, date: LocalDateTime = LocalDateTime.now()) : this(
        date, food.name, grams, food.kcal * grams / 100,
        food.protein?.times(grams / 100), food.carbs?.times(grams / 100), food.fat?.times(grams / 100),
    )

    fun toJson(): JSONObject = JSONObject().put("id", id).put("date", date.toString()).put("name", name)
        .put("grams", grams).put("kcal", kcal).put("protein", protein).put("carbs", carbs).put("fat", fat)
        .put("comment", comment)

    companion object {
        fun fromJson(o: JSONObject): Entry {
            fun d(k: String) = if (o.isNull(k)) null else o.getDouble(k)
            return Entry(LocalDateTime.parse(o.getString("date")), o.getString("name"), o.getDouble("grams"),
                o.getDouble("kcal"), d("protein"), d("carbs"), d("fat"),
                if (o.isNull("comment")) null else o.getString("comment"), o.getString("id"))
        }
    }
}

enum class Tone { gentile, diretto }
enum class Goal { dimagrire, mantenere, aumentare }
enum class Sex { uomo, donna }

enum class Activity(val factor: Double, val label: String) {
    sedentario(1.2, "Sedentario (ufficio, poco movimento)"),
    leggero(1.375, "Leggero (sport 1–3 volte a settimana)"),
    moderato(1.55, "Moderato (sport 3–5 volte a settimana)"),
    intenso(1.725, "Intenso (sport 6–7 volte a settimana)"),
}

/** Dati dell'utente e obiettivi. */
data class Profile(
    val sex: Sex = Sex.uomo,
    val age: Int = 30,
    val height: Double = 175.0,
    val weight: Double = 75.0,
    val activity: Activity = Activity.leggero,
    val goal: Goal = Goal.mantenere,
    val checkHour: Int = 18,
    val threshold: Double? = null,  // null = soglia calcolata
) {
    /** Metabolismo basale, formula di Mifflin-St Jeor. */
    val bmr get() = 10 * weight + 6.25 * height - 5 * age + if (sex == Sex.uomo) 5 else -161
    val tdee get() = bmr * activity.factor
    val target get() = when (goal) {
        Goal.dimagrire -> max(tdee - 500, bmr)  // mai sotto il basale
        Goal.mantenere -> tdee
        Goal.aumentare -> tdee + 300
    }
    val protein get() = weight * if (goal == Goal.mantenere) 1.2 else 1.8
    /** Aumentare: entro l'ora del controllo almeno il 60% del target. Dimagrire: non oltre il 75%. */
    val effectiveThreshold get() = threshold ?: (target * if (goal == Goal.aumentare) 0.6 else 0.75).roundToInt().toDouble()

    fun save(p: SharedPreferences) = p.edit().putString("sex", sex.name).putInt("age", age)
        .putFloat("height", height.toFloat()).putFloat("weight", weight.toFloat())
        .putString("activity", activity.name).putString("goal", goal.name).putInt("checkHour", checkHour)
        .putFloat("threshold", threshold?.toFloat() ?: -1f).putBoolean("hasProfile", true).apply()

    companion object {
        fun load(p: SharedPreferences): Profile? = if (!p.getBoolean("hasProfile", false)) null else Profile(
            Sex.valueOf(p.getString("sex", null)!!), p.getInt("age", 30),
            p.getFloat("height", 175f).toDouble(), p.getFloat("weight", 75f).toDouble(),
            Activity.valueOf(p.getString("activity", null)!!), Goal.valueOf(p.getString("goal", null)!!),
            p.getInt("checkHour", 18), p.getFloat("threshold", -1f).takeIf { it >= 0 }?.toDouble(),
        )
    }
}

/** Stato dell'app osservabile da Compose: diario in un file JSON, profilo e tono nelle preferenze. */
object Store {
    val entries = mutableStateListOf<Entry>()
    var foods: List<Food> = emptyList(); private set
    var profile by mutableStateOf<Profile?>(null); private set  // null = onboarding
    var tone by mutableStateOf(Tone.gentile); private set
    private lateinit var file: File
    private lateinit var prefs: SharedPreferences

    fun init(ctx: Context) {
        if (::file.isInitialized) return
        prefs = ctx.getSharedPreferences("grillo", Context.MODE_PRIVATE)
        file = File(ctx.filesDir, "entries.json")
        foods = Food.parse(ctx.assets.open("foods.json").bufferedReader().readText())
        profile = Profile.load(prefs)
        tone = Tone.valueOf(prefs.getString("tone", Tone.gentile.name)!!)
        if (file.exists()) {
            val arr = JSONArray(file.readText())
            entries.addAll((0 until arr.length()).map { Entry.fromJson(arr.getJSONObject(it)) })
        }
    }

    fun setProfile(ctx: Context, p: Profile) { profile = p; p.save(prefs); Reminder.schedule(ctx) }
    fun chooseTone(t: Tone) { tone = t; prefs.edit().putString("tone", t.name).apply() }

    fun add(e: Entry) { entries.add(e); save() }
    fun delete(e: Entry) { entries.removeAll { it.id == e.id }; save() }
    fun setComment(id: String, comment: String?) {
        val i = entries.indexOfFirst { it.id == id }.takeIf { it >= 0 } ?: return
        entries[i] = entries[i].copy(comment = comment); save()
    }

    // shortcut: riscrive tutto il file a ogni modifica, va bene fino a qualche migliaio di voci; oltre passare a Room
    private fun save() {
        val tmp = File(file.path + ".tmp")
        tmp.writeText(JSONArray(entries.map { it.toJson() }).toString())
        tmp.renameTo(file)  // scrittura atomica: un crash a metà non corrompe il diario
    }

    fun todayKcal() = entries.filter { it.day == LocalDate.now() }.sumOf { it.kcal }
}

val Double.g get() = "${roundToInt()} g"
val Double?.g get() = this?.g ?: "n.d."
fun String.cap() = replaceFirstChar { it.uppercase() }
