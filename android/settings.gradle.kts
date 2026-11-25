pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "tally-monitor-android"
include(":core", ":credentials", ":security", ":api", ":storage", ":sync", ":analysis", ":export", ":services", ":testing", ":verify", ":app")
