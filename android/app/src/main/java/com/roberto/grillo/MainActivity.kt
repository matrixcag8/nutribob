package com.roberto.grillo

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddCircle
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

val Green = Color(0xFF34C759)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Store.init(this)
        LocalModel.refresh(this)
        Reminder.schedule(this)
        setContent {
            val dark = isSystemInDarkTheme()
            MaterialTheme(if (dark) darkColorScheme(primary = Green) else lightColorScheme(primary = Green)) { Root() }
        }
    }
}

private enum class Tab(val label: String) { Home("Home"), Diary("Diario"), Profile("Profilo") }

@Composable
private fun Root() {
    val ctx = LocalContext.current
    var tab by rememberSaveable { mutableStateOf(Tab.Home) }
    var adding by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(Unit) { LocalModel.resume(ctx) }

    if (Store.profile == null) { OnboardingScreen(); return }

    Scaffold(bottomBar = {
        NavigationBar {
            NavigationBarItem(tab == Tab.Home, { tab = Tab.Home }, { Icon(Icons.Filled.Home, null) }, label = { Text("Home") })
            NavigationBarItem(tab == Tab.Diary, { tab = Tab.Diary }, { Icon(Icons.Filled.List, null) }, label = { Text("Diario") })
            // il + al centro apre l'aggiunta invece di cambiare tab
            NavigationBarItem(false, { adding = true }, { Icon(Icons.Filled.AddCircle, null) }, label = { Text("Aggiungi") })
            NavigationBarItem(tab == Tab.Profile, { tab = Tab.Profile }, { Icon(Icons.Filled.Person, null) }, label = { Text("Profilo") })
        }
    }) { pad ->
        val m = Modifier.padding(pad)
        when (tab) {
            Tab.Home -> HomeScreen(m)
            Tab.Diary -> DiaryScreen(m)
            Tab.Profile -> SettingsScreen(m)
        }
    }
    if (adding) AddFoodSheet { adding = false }
}
