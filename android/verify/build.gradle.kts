plugins {
    alias(libs.plugins.kotlin.jvm)
    application
}

kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

dependencies {
    implementation(project(":core"))
    implementation(project(":credentials"))
    implementation(project(":api"))
    implementation(project(":sync"))
    implementation(project(":analysis"))
    implementation(project(":export"))
}

application { mainClass.set("ar.tallymonitor.verify.MainKt") }

// ./gradlew :verify:run  → compara todo contra los vectores generados por la referencia Python (golden/) y revisa la arquitectura.
tasks.named<JavaExec>("run") { args(rootProject.file("golden").path) }

// ./gradlew check ejecuta la misma verificación.
tasks.register<JavaExec>("verifyAll") {
    group = "verification"
    classpath = sourceSets["main"].runtimeClasspath
    mainClass.set("ar.tallymonitor.verify.MainKt")
    args(rootProject.file("golden").path)
}
tasks.named("check") { dependsOn("verifyAll") }
