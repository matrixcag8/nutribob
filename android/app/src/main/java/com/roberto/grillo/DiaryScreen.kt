package com.roberto.grillo

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.time.format.DateTimeFormatter
import java.util.Locale

private val dayFmt = DateTimeFormatter.ofPattern("EEEE d MMMM", Locale.ITALIAN)

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun DiaryScreen(modifier: Modifier) {
    val days = Store.entries.sortedByDescending { it.date }.groupBy { it.day }
    if (days.isEmpty()) {
        Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Diario vuoto", style = MaterialTheme.typography.titleLarge)
                Text("Segna cosa hai mangiato con +")
            }
        }
        return
    }
    LazyColumn(modifier.fillMaxSize()) {
        item { Text("Diario", Modifier.padding(16.dp), style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold) }
        days.forEach { (day, items) ->
            stickyHeader(key = day.toString()) {
                Column(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceVariant).padding(horizontal = 16.dp, vertical = 8.dp)) {
                    Text(day.format(dayFmt).cap(), style = MaterialTheme.typography.labelLarge)
                    Text("${items.sumOf { it.kcal }.toInt()} kcal · P ${items.sumOf { it.protein ?: 0.0 }.g} · " +
                        "C ${items.sumOf { it.carbs ?: 0.0 }.g} · G ${items.sumOf { it.fat ?: 0.0 }.g}",
                        style = MaterialTheme.typography.bodySmall)
                }
            }
            items(items, key = { it.id }) { EntryRow(it); HorizontalDivider() }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun EntryRow(entry: Entry) {
    var menu by remember { mutableStateOf(false) }
    // tieni premuto per eliminare (su iOS è lo swipe)
    Column(Modifier.fillMaxWidth().combinedClickable(onClick = {}, onLongClick = { menu = true }).padding(16.dp)) {
        Row {
            Text(entry.name.cap(), style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.weight(1f))
            Text("${entry.kcal.toInt()} kcal")
        }
        Text("${entry.grams.g} · P ${entry.protein.g} · C ${entry.carbs.g} · G ${entry.fat.g}", style = MaterialTheme.typography.bodySmall)
        entry.comment?.let {
            Text("🦗 $it", Modifier.padding(top = 4.dp).fillMaxWidth()
                .background(Green.copy(alpha = 0.12f), RoundedCornerShape(8.dp)).padding(8.dp), fontStyle = FontStyle.Italic)
        }
        DropdownMenu(menu, { menu = false }) {
            DropdownMenuItem({ Text("Elimina") }, { Store.delete(entry); menu = false })
        }
    }
}
