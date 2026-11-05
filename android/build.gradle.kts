plugins {
    id("com.android.application") version "9.5.0" apply false
    // LiteRT-LM 0.19 è compilato con Kotlin 2.4: forza il KGP che usa il Kotlin integrato di AGP
    id("org.jetbrains.kotlin.android") version "2.4.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.4.21" apply false
}
