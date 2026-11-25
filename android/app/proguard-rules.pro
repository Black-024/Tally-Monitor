# La app no usa reflexión. R8 puede ofuscar todo; solo se conservan los nombres de las excepciones tipadas para los mensajes.
-keep class ar.tallymonitor.core.ErrorCode { *; }
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
