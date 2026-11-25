package ar.tallymonitor.core

/**
 * Texto secreto (la API Key). Nunca se muestra: `toString()` devuelve «***». Solo `reveal()` entrega el valor,
 * y las pruebas de arquitectura limitan quién puede llamarlo (el cliente de red y el protector de credenciales).
 */
class Secret(private val value: String) {
    fun reveal(): String = value
    /** Forma de una clave de Tally («tly-» + caracteres imprimibles, sin espacios), sin revelar el valor. */
    fun hasTallyKeyShape(): Boolean = value.length <= 200 && Regex("^tly-[\\x21-\\x7e]{4,}$").matches(value)
    override fun toString(): String = "***"
    override fun equals(other: Any?): Boolean = other is Secret && other.value == value
    override fun hashCode(): Int = value.hashCode()
}
