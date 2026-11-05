package com.roberto.grillo

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale

private val Orange = Color(0xFFFF9500)

@Composable
fun HomeScreen(modifier: Modifier) {
    val profile = Store.profile ?: return
    val entries = Store.entries
    val today = entries.filter { it.day == LocalDate.now() }
    val kcal = today.sumOf { it.kcal }
    val week = lastDays(7, entries)
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()

    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Oggi", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)

        if (!LocalModel.downloaded) CardBox {
            val p = LocalModel.progress
            if (p != null) {
                Text("Scarico il cervello del grillo… ${(p * 100).toInt()}%")
                LinearProgressIndicator({ p }, Modifier.fillMaxWidth())
            } else {
                Button({ scope.launch { LocalModel.download(ctx) } }) { Text("Scarica il cervello del grillo (~1 GB)") }
            }
            LocalModel.error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            Text("Serve una volta sola, meglio in Wi-Fi. Poi il grillo funziona offline.", style = MaterialTheme.typography.bodySmall)
        }

        CardBox {
            Row(horizontalArrangement = Arrangement.spacedBy(20.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(130.dp), contentAlignment = Alignment.Center) {
                    Ring((kcal / profile.target).toFloat())
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("${kcal.toInt()}", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                        Text("di ${profile.target.toInt()} kcal", style = MaterialTheme.typography.bodySmall)
                    }
                }
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    MacroBar("Proteine", today.sumOf { it.protein ?: 0.0 }, profile.protein, Orange)
                    MacroBar("Carboidrati", today.sumOf { it.carbs ?: 0.0 }, null, Color.Blue)
                    MacroBar("Grassi", today.sumOf { it.fat ?: 0.0 }, null, Color.Magenta)
                }
            }
            Text(if (kcal <= profile.target) "Mancano ${(profile.target - kcal).toInt()} kcal al tuo obiettivo di oggi."
                 else "Sei ${(kcal - profile.target).toInt()} kcal sopra l'obiettivo di oggi.",
                style = MaterialTheme.typography.bodyMedium)
        }

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            val avg = week.sumOf { it.second } / maxOf(1, week.count { it.second > 0 })
            Stat("${streak(entries)}", "giorni di fila")
            Stat("${avg.toInt()}", "media kcal 7 gg")
            Stat("${today.size}", "voci oggi")
        }

        CardBox {
            Text("Ultimi 7 giorni", style = MaterialTheme.typography.titleMedium)
            WeekChart(week, profile.target)
        }

        entries.filter { it.comment != null }.maxByOrNull { it.date }?.let { last ->
            CardBox {
                Text("🦗 Il grillo dice", style = MaterialTheme.typography.titleMedium, color = Green)
                Text(last.comment!!, fontStyle = FontStyle.Italic)
                Text("su ${last.name}", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

/** kcal per giorno degli ultimi n giorni, oggi compreso (anche i giorni vuoti). */
fun lastDays(n: Int, entries: List<Entry>, now: LocalDate = LocalDate.now()) =
    (n - 1 downTo 0).map { off -> now.minusDays(off.toLong()).let { d -> d to entries.filter { it.day == d }.sumOf { it.kcal } } }

/** Giorni consecutivi con almeno una voce; oggi vuoto non interrompe la serie. */
fun streak(entries: List<Entry>, now: LocalDate = LocalDate.now()): Int {
    val days = entries.map { it.day }.toSet()
    var day = if (now in days) now else now.minusDays(1)
    var count = 0
    while (day in days) { count++; day = day.minusDays(1) }
    return count
}

@Composable
fun CardBox(content: @Composable ColumnScope.() -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
    }
}

@Composable
private fun Ring(value: Float) {
    val v by animateFloatAsState(value.coerceAtMost(1f), label = "ring")
    val color = if (value > 1) Orange else Green
    Canvas(Modifier.fillMaxSize().padding(7.dp)) {
        val stroke = Stroke(14.dp.toPx(), cap = StrokeCap.Round)
        drawArc(Green.copy(alpha = 0.15f), 0f, 360f, false, style = stroke)
        drawArc(color, -90f, 360f * v, false, style = stroke)
    }
}

@Composable
private fun MacroBar(name: String, value: Double, target: Double?, color: Color) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth()) {
            Text(name, style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.weight(1f))
            Text(target?.let { "${value.toInt()}/${it.toInt()} g" } ?: "${value.toInt()} g", style = MaterialTheme.typography.bodySmall)
        }
        if (target != null) LinearProgressIndicator({ (value / target).toFloat().coerceAtMost(1f) }, Modifier.fillMaxWidth(), color = color)
    }
}

@Composable
private fun androidx.compose.foundation.layout.RowScope.Stat(value: String, label: String) {
    Card(Modifier.weight(1f)) {
        Column(Modifier.fillMaxWidth().padding(vertical = 12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(value, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(label, style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.Center)
        }
    }
}

@Composable
private fun WeekChart(week: List<Pair<LocalDate, Double>>, target: Double) {
    val line = MaterialTheme.colorScheme.onSurfaceVariant
    val max = maxOf(target, week.maxOf { it.second }) * 1.1
    Canvas(Modifier.fillMaxWidth().height(140.dp)) {
        val slot = size.width / week.size
        week.forEachIndexed { i, (_, k) ->
            val h = (k / max * size.height).toFloat()
            drawRoundRect(Green, Offset(i * slot + slot * 0.2f, size.height - h), Size(slot * 0.6f, h), CornerRadius(4.dp.toPx()))
        }
        val y = (size.height - target / max * size.height).toFloat()
        drawLine(line, Offset(0f, y), Offset(size.width, y), 1.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(12f, 12f)))
    }
    Row(Modifier.fillMaxWidth()) {
        week.forEach { (d, _) ->
            Text(d.dayOfWeek.getDisplayName(TextStyle.NARROW, Locale.ITALIAN), Modifier.weight(1f),
                textAlign = TextAlign.Center, style = MaterialTheme.typography.bodySmall)
        }
    }
    Text("- - - obiettivo ${target.toInt()} kcal", style = MaterialTheme.typography.labelSmall, color = line)
}
