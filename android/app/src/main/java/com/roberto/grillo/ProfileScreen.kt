package com.roberto.grillo

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp

/** Dati e obiettivi dell'utente: usato al primo avvio e nelle impostazioni. */
@Composable
fun ProfileForm(profile: Profile, onChange: (Profile) -> Unit) {
    // cambiando obiettivo la soglia torna quella calcolata
    val set = { p: Profile -> onChange(if (p.goal != profile.goal) p.copy(threshold = null) else p) }

    Section("Chi sei")
    Segmented(Sex.entries, profile.sex) { set(profile.copy(sex = it)) }
    StepperRow("Età: ${profile.age} anni", profile.age, 14..100) { set(profile.copy(age = it)) }
    NumberField("Altezza (cm)", profile.height) { set(profile.copy(height = it)) }
    NumberField("Peso (kg)", profile.weight) { set(profile.copy(weight = it)) }
    Text("Attività", style = MaterialTheme.typography.labelLarge)
    Activity.entries.forEach { a ->
        Row(Modifier.fillMaxWidth().selectable(profile.activity == a) { set(profile.copy(activity = a)) },
            verticalAlignment = Alignment.CenterVertically) {
            RadioButton(profile.activity == a, null)
            Text(a.label, Modifier.padding(start = 8.dp))
        }
    }

    Section("Obiettivo")
    Segmented(Goal.entries, profile.goal) { set(profile.copy(goal = it)) }
    Line("Calorie al giorno", "${profile.target.toInt()} kcal")
    Line("Proteine al giorno", "${profile.protein.toInt()} g")
    Footer("Stima con la formula di Mifflin-St Jeor: è un punto di partenza, non una prescrizione.")

    if (profile.goal != Goal.mantenere) {
        Section("Il grillo ti richiama")
        StepperRow("Controllo alle ${profile.checkHour}:00", profile.checkHour, 8..22) { set(profile.copy(checkHour = it)) }
        // la key fa ripartire il campo quando la soglia calcolata cambia (es. nuovo obiettivo)
        androidx.compose.runtime.key(profile.goal, profile.threshold == null) {
            NumberField("Soglia (kcal)", profile.effectiveThreshold) { set(profile.copy(threshold = it)) }
        }
        Footer(if (profile.goal == Goal.aumentare) "Se a quell'ora sei sotto la soglia, ti arriva una notifica."
               else "Se a quell'ora hai già superato la soglia, ti arriva una notifica.")
    }
}

@Composable
fun OnboardingScreen() {
    val ctx = LocalContext.current
    var profile by remember { mutableStateOf(Profile()) }
    val askNotifications = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
    Surface {
        Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("I tuoi obiettivi", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
            Text("Ciao, sono il grillo. Prima di cominciare dimmi qualcosa di te e cosa vuoi ottenere: così so quando richiamarti.")
            ProfileForm(profile) { profile = it }
            Button({
                if (Build.VERSION.SDK_INT >= 33) askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
                Store.setProfile(ctx, profile)
            }, Modifier.fillMaxWidth(), enabled = profile.height >= 100 && profile.weight >= 30) { Text("Inizia") }
        }
    }
}

@Composable
fun SettingsScreen(modifier: Modifier) {
    val ctx = LocalContext.current
    val profile = Store.profile ?: return
    Column(modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Profilo", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Section("Carattere del grillo")
        Tone.entries.forEach { t ->
            Row(Modifier.fillMaxWidth().selectable(Store.tone == t) { Store.chooseTone(t) }, verticalAlignment = Alignment.CenterVertically) {
                RadioButton(Store.tone == t, null)
                Text(t.name.cap(), Modifier.padding(start = 8.dp))
            }
        }
        ProfileForm(profile) { Store.setProfile(ctx, it) }
        Section("Fonti")
        Footer("Valori nutrizionali per 100 g dalle tabelle di NutriBob. \"n.d.\" = macro non ancora disponibili.")
    }
}

@Composable
private fun Section(title: String) =
    Text(title.uppercase(), Modifier.padding(top = 16.dp), style = MaterialTheme.typography.labelMedium, color = Green)

@Composable
private fun Footer(text: String) =
    Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun <T : Enum<T>> Segmented(options: List<T>, selected: T, onSelect: (T) -> Unit) {
    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
        options.forEachIndexed { i, o ->
            SegmentedButton(o == selected, { onSelect(o) }, SegmentedButtonDefaults.itemShape(i, options.size)) { Text(o.name.cap()) }
        }
    }
}

@Composable
private fun StepperRow(label: String, value: Int, range: IntRange, onChange: (Int) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label)
        Spacer(Modifier.weight(1f))
        TextButton({ onChange(value - 1) }, enabled = value > range.first) { Text("−", style = MaterialTheme.typography.titleLarge) }
        TextButton({ onChange(value + 1) }, enabled = value < range.last) { Text("+", style = MaterialTheme.typography.titleLarge) }
    }
}

/** Campo numerico: il testo resta quello digitato, il valore passa solo quando è un numero valido. */
@Composable
private fun NumberField(label: String, value: Double, onChange: (Double) -> Unit) {
    var text by remember { mutableStateOf(if (value % 1 == 0.0) value.toInt().toString() else value.toString()) }
    OutlinedTextField(text, { t ->
        text = t
        t.replace(',', '.').toDoubleOrNull()?.let(onChange)
    }, Modifier.fillMaxWidth(), label = { Text(label) }, singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
}
