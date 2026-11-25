import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

// Firma de release: se lee de keystore.properties (nunca se sube a Git) o de variables de entorno.
val ksProps = Properties().apply { rootProject.file("keystore.properties").takeIf { it.exists() }?.inputStream()?.use { load(it) } }
fun sign(name: String, env: String) = ksProps.getProperty(name) ?: System.getenv(env)

android {
    namespace = "ar.tallymonitor.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "ar.tallymonitor"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
    }

    signingConfigs {
        create("release") {
            val file = sign("storeFile", "TM_STORE_FILE")
            if (file != null) {
                storeFile = rootProject.file(file).takeIf { it.exists() } ?: File(file)
                storePassword = sign("storePassword", "TM_STORE_PASSWORD")
                keyAlias = sign("keyAlias", "TM_KEY_ALIAS")
                keyPassword = sign("keyPassword", "TM_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (sign("storeFile", "TM_STORE_FILE") != null) signingConfig = signingConfigs.getByName("release")
        }
        debug { applicationIdSuffix = ".debug"; versionNameSuffix = "-debug" }
    }

    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    implementation(project(":services"))
    implementation(project(":core"))
    implementation(project(":analysis"))
    implementation(project(":export"))
    debugImplementation(project(":testing"))

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.androidx.work.runtime.ktx)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.foundation)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui.tooling.preview)
    debugImplementation(libs.androidx.compose.ui.tooling)
}
