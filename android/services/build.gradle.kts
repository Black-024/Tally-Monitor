plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "ar.tallymonitor.services"
    compileSdk = 35
    defaultConfig { minSdk = 26 }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    api(project(":core"))
    api(project(":analysis"))
    api(project(":export"))
    implementation(project(":credentials"))
    implementation(project(":security"))
    implementation(project(":storage"))
    implementation(project(":sync"))
    implementation(project(":api"))
    api(libs.kotlinx.coroutines.core)
    testImplementation(libs.junit)
}
