package com.roberto.grillo

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/** Il commento arriva dopo che la sheet si è chiusa, quindi gira fuori dal ciclo di vita della UI. */
private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddFoodSheet(onDismiss: () -> Unit) {
    var selected by remember { mutableStateOf<Food?>(null) }
    ModalBottomSheet(onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        val food = selected
        if (food == null) FoodList { selected = it }
        else {
            BackHandler { selected = null }
            QuantityForm(food, onBack = { selected = null }, onSaved = onDismiss)
        }
    }
}

@Composable
private fun FoodList(onPick: (Food) -> Unit) {
    var query by remember { mutableStateOf("") }
    val results = Store.foods.filter { query.isBlank() || it.name.contains(query.trim(), ignoreCase = true) }
    Column(Modifier.fillMaxSize().imePadding()) {
        Text("Cosa hai mangiato?", Modifier.padding(horizontal = 16.dp), style = MaterialTheme.typography.titleLarge)
        OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth().padding(16.dp),
            placeholder = { Text("Cerca alimento") }, singleLine = true)
        LazyColumn {
            items(results, key = { it.name }) { food ->
                Row(Modifier.fillMaxWidth().clickable { onPick(food) }.padding(16.dp)) {
                    Text(food.name.cap())
                    Spacer(Modifier.weight(1f))
                    Text("${food.kcal.toInt()} kcal/100 g", style = MaterialTheme.typography.bodySmall)
                }
                HorizontalDivider()
            }
        }
    }
}

@Composable
private fun QuantityForm(food: Food, onBack: () -> Unit, onSaved: () -> Unit) {
    val ctx = LocalContext.current.applicationContext
    var text by remember { mutableStateOf(food.portion.toInt().toString()) }
    val grams = text.replace(',', '.').toDoubleOrNull() ?: 0.0
    val preview = Entry(food, grams)

    Column(Modifier.fillMaxWidth().padding(16.dp).imePadding()) {
        Row {
            TextButton(onBack) { Text("‹ Indietro") }
            Spacer(Modifier.weight(1f))
            Button({
                val entry = Entry(food, grams)
                Store.add(entry)
                val history = Store.entries.filter { it.date > entry.date.minusDays(7) }
                val tone = Store.tone
                val profile = Store.profile!!
                appScope.launch { Grillo.comment(ctx, entry, history, tone, profile)?.let { Store.setComment(entry.id, it) } }
                onSaved()
            }, enabled = grams > 0) { Text("Segna") }
        }
        Text(food.name.cap(), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        OutlinedTextField(text, { text = it }, Modifier.fillMaxWidth().padding(vertical = 8.dp),
            label = { Text("Quantità in grammi") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
        TextButton({ text = food.portion.toInt().toString() }) { Text("Porzione standard: ${food.portionLabel} (${food.portion.g})") }
        Line("Calorie", "${preview.kcal.toInt()} kcal")
        Line("Proteine", preview.protein.g)
        Line("Carboidrati", preview.carbs.g)
        Line("Grassi", preview.fat.g)
    }
}

@Composable
fun Line(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Text(label)
        Spacer(Modifier.weight(1f))
        Text(value, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
