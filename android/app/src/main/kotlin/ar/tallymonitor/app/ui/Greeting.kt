package ar.tallymonitor.app.ui

import java.time.DayOfWeek
import java.time.LocalDateTime

data class Greeting(val title: String, val subtitle: String)

/** Mensaje de la pestaña Inicio según fecha y hora locales. Fechas especiales primero; si no, momento del día y día de la semana. Función pura (se puede probar). */
fun greetingFor(now: LocalDateTime): Greeting {
    val m = now.monthValue
    val d = now.dayOfMonth
    special(m, d)?.let { return it }
    val title = when (now.hour) {
        in 0..4 -> tr("Trasnochando con las encuestas", "Up late with your surveys")
        in 5..11 -> tr("¡Buen día!", "Good morning!")
        in 12..19 -> tr("¡Buenas tardes!", "Good afternoon!")
        else -> tr("¡Buenas noches!", "Good evening!")
    }
    val sub = when (now.dayOfWeek) {
        DayOfWeek.MONDAY -> tr("Arrancó la semana: a ver cómo vienen las encuestas.", "New week: let's see how the surveys are doing.")
        DayOfWeek.TUESDAY -> tr("Martes de números: ¿cuántas respuestas hubo?", "Tuesday numbers: how many responses came in?")
        DayOfWeek.WEDNESDAY -> tr("Mitad de semana. ¿Cómo van las encuestas?", "Midweek. How are the surveys going?")
        DayOfWeek.THURSDAY -> tr("Jueves: casi llegando al finde. ¿Alguna novedad?", "Thursday: almost the weekend. Any news?")
        DayOfWeek.FRIDAY -> tr("Viernes: una última mirada antes del finde.", "Friday: one last look before the weekend.")
        DayOfWeek.SATURDAY -> tr("Sábado: ¿mirando encuestas igual? Me gusta.", "Saturday: checking surveys anyway? Love it.")
        DayOfWeek.SUNDAY -> tr("Domingo tranqui. Las encuestas no se cansan.", "Easy Sunday. Surveys never get tired.")
    }
    return Greeting(title, sub)
}

private fun special(m: Int, d: Int): Greeting? = when {
    m == 12 && (d == 24 || d == 25) -> Greeting(tr("¡Feliz Navidad!", "Merry Christmas!"), tr("¿Encuestas navideñas? Mirá cómo les está yendo.", "Christmas surveys? See how they're doing."))
    m == 12 && d == 31 -> Greeting(tr("Último día del año", "Last day of the year"), tr("¿Un balance de las encuestas antes del brindis?", "A survey recap before the toast?"))
    m == 1 && d == 1 -> Greeting(tr("¡Feliz año nuevo!", "Happy New Year!"), tr("Empezá el año viendo cómo arrancan tus encuestas.", "Start the year by seeing how your surveys are kicking off."))
    m == 2 && d == 14 -> Greeting(tr("Día de los Enamorados", "Valentine's Day"), tr("¿Una encuesta sobre el amor? Preguntar no cuesta nada.", "A survey about love? Asking is free."))
    m == 5 && d == 1 -> Greeting(tr("Día del Trabajador", "Workers' Day"), tr("Hoy se descansa, pero las respuestas siguen llegando.", "Today is for resting, but responses keep coming in."))
    m == 5 && d == 25 -> Greeting(tr("¡Feliz 25 de Mayo!", "Happy May 25th!"), tr("Un día patrio para mirar qué opina la gente.", "A national holiday to see what people think."))
    m == 7 && d == 9 -> Greeting(tr("¡Feliz Día de la Independencia!", "Happy Argentine Independence Day!"), tr("Fecha ideal para una encuesta de opinión.", "A great date for an opinion survey."))
    m == 7 && d == 20 -> Greeting(tr("¡Feliz Día del Amigo!", "Happy Friend's Day!"), tr("¿Les mandaste la encuesta a tus amigos?", "Did you send the survey to your friends?"))
    m == 10 && d == 31 -> Greeting(tr("¡Feliz Halloween!", "Happy Halloween!"), tr("¿Encuestas de terror? Revisá si hay respuestas misteriosas.", "Scary surveys? Check for mysterious responses."))
    m == 12 && d in 26..30 -> Greeting(tr("Entre Navidad y Año Nuevo", "Between Christmas and New Year"), tr("Semana lenta: buen momento para revisar resultados.", "Slow week: a good time to review results."))
    else -> null
}
