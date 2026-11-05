plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.roberto.grillo"
    compileSdk = 37
    defaultConfig {
        applicationId = "com.roberto.grillo"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1"
        ndk { abiFilters += "arm64-v8a" }  // il OnePlus 6T è arm64; evita i 27 MB della lib x86_64
    }
    buildFeatures { compose = true }
    packaging { jniLibs { useLegacyPackaging = true } }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2026.09.00"))
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core:1.7.8")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("com.google.ai.edge.litertlm:litertlm-android:0.19.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20260814")  // org.json di android.jar è solo uno stub nei test JVM
}
