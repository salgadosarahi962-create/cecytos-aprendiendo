import os
import re
import sqlite3
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
# En producción define la variable de entorno SECRET_KEY con un valor largo y aleatorio.
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "usuarios.db")


# ---------------------------------------------------------------
# CONTENIDO DE LAS MATERIAS
# Para agregar o editar temas, edita las listas de abajo.
# Cada quiz es una lista de (pregunta, [opciones], índice_correcto).
# "video" es el ID de YouTube (lo que va después de v= en el enlace);
# déjalo vacío "" si todavía no tienes uno.
# ---------------------------------------------------------------
def tema(titulo, explicacion, puntos, ejemplo, practica, respuesta, quiz, video=""):
    return {
        "titulo": titulo,
        "explicacion": explicacion,
        "puntos": puntos,
        "ejemplo": ejemplo,
        "practica": practica,
        "respuesta": respuesta,
        "quiz": [{"pregunta": p, "opciones": o, "correcta": c} for p, o, c in quiz],
        "video": video,
    }


MATERIAS = {
    "matematicas": {
        "nombre": "Matemáticas",
        "temas": [
            tema(
                "Números y valor posicional",
                "En un número, cada cifra vale según el lugar que ocupa: unidades, decenas, centenas y millares.",
                [
                    "Se leen de derecha a izquierda: unidades, decenas, centenas, millares.",
                    "Cada lugar vale 10 veces más que el que está a su derecha.",
                    "El 0 sirve para ocupar un lugar vacío.",
                ],
                "En 3 482: 3 millares + 4 centenas + 8 decenas + 2 unidades = 3 000 + 400 + 80 + 2.",
                "¿Cuánto vale el 7 en el número 5 704?",
                "Vale 700, porque está en el lugar de las centenas.",
                [
                    ("¿Cuántas decenas tiene el número 56?", ["5", "6", "50"], 0),
                    ("En 4 209, ¿qué lugar ocupa el 2?", ["Decenas", "Centenas", "Millares"], 1),
                ],
            ),
            tema(
                "Suma y resta",
                "Sumar es juntar cantidades; restar es quitar una cantidad a otra. Son operaciones inversas.",
                [
                    "Al sumar, el orden no cambia el resultado: 3 + 5 = 5 + 3.",
                    "Al restar, el orden sí importa: 8 − 3 no es igual a 3 − 8.",
                    "Una resta se comprueba sumando: si 9 − 4 = 5, entonces 5 + 4 = 9.",
                ],
                "Tienes 25 canicas y ganas 12: 25 + 12 = 37. Luego regalas 7: 37 − 7 = 30.",
                "Ana tenía 48 stickers y le regalaron 15. ¿Cuántos tiene ahora?",
                "48 + 15 = 63 stickers.",
                [
                    ("¿Cuánto es 70 − 25?", ["45", "55", "95"], 0),
                    ("¿Qué operación comprueba que 12 − 5 = 7?",
                     ["7 + 5 = 12", "7 − 5 = 12", "12 + 5 = 7"], 0),
                ],
            ),
            tema(
                "Multiplicación",
                "Multiplicar es sumar el mismo número varias veces. 4 × 3 significa sumar 4 tres veces.",
                [
                    "4 × 3 = 4 + 4 + 4 = 12.",
                    "El orden no cambia el resultado: 4 × 3 = 3 × 4.",
                    "Cualquier número por 0 da 0, y por 1 da el mismo número.",
                ],
                "Si cada caja tiene 6 lápices y hay 5 cajas: 6 × 5 = 30 lápices.",
                "Una bolsa tiene 8 dulces. ¿Cuántos dulces hay en 7 bolsas?",
                "8 × 7 = 56 dulces.",
                [
                    ("¿Cuánto es 9 × 6?", ["54", "45", "63"], 0),
                    ("¿Cuánto es 15 × 0?", ["15", "1", "0"], 2),
                ],
            ),
            tema(
                "División",
                "Dividir es repartir una cantidad en partes iguales. Es la operación inversa de la multiplicación.",
                [
                    "En 20 ÷ 4 = 5: 20 es el dividendo, 4 el divisor y 5 el cociente.",
                    "Se comprueba multiplicando: 5 × 4 = 20.",
                    "A veces sobra algo; eso se llama residuo.",
                ],
                "Repartir 17 galletas entre 5 niños: cada uno recibe 3 y sobran 2 (17 = 5 × 3 + 2).",
                "Se reparten 36 manzanas en 9 canastas iguales. ¿Cuántas van en cada canasta?",
                "36 ÷ 9 = 4 manzanas.",
                [
                    ("¿Cuánto es 42 ÷ 6?", ["6", "7", "8"], 1),
                    ("En 20 ÷ 4 = 5, ¿cómo se llama el 5?", ["Divisor", "Dividendo", "Cociente"], 2),
                ],
            ),
            tema(
                "Fracciones",
                "Una fracción representa una o varias partes iguales de un entero. Se escribe con numerador (arriba) y denominador (abajo).",
                [
                    "El denominador dice en cuántas partes iguales se divide el entero.",
                    "El numerador dice cuántas de esas partes se toman.",
                    "Fracciones con el mismo denominador se suman sumando los numeradores.",
                ],
                "Una pizza tiene 8 porciones. Si comes 3, comiste 3/8. Y 3/8 + 2/8 = 5/8.",
                "¿Cuánto es 2/5 + 1/5?",
                "3/5.",
                [
                    ("En 3/4, ¿cuál es el denominador?", ["3", "4", "7"], 1),
                    ("¿Cuánto es 1/6 + 4/6?", ["5/12", "5/6", "4/6"], 1),
                ],
            ),
            tema(
                "Números decimales",
                "Los decimales tienen una parte entera y una parte decimal separadas por un punto. Sirven para expresar cantidades menores que uno, como el dinero.",
                [
                    "El primer lugar después del punto son los décimos; el segundo, los centésimos.",
                    "0.5 es lo mismo que 1/2.",
                    "Al sumar decimales, alinea los puntos decimales.",
                ],
                "2.35 + 1.40 = 3.75.",
                "¿Cuánto es 4.5 + 2.75?",
                "7.25.",
                [
                    ("¿Cuál número es mayor?", ["0.5", "0.45", "0.05"], 0),
                    ("¿Cuánto es 1.2 + 0.8?", ["1.10", "2.0", "2.2"], 1),
                ],
            ),
            tema(
                "Porcentajes",
                "Un porcentaje indica cuántas partes de cada 100 se toman. Se escribe con el símbolo %.",
                [
                    "50 % es la mitad y 25 % es la cuarta parte.",
                    "Para calcular el 10 %, divide entre 10.",
                    "Para calcular un porcentaje: multiplica la cantidad por el porcentaje y divide entre 100.",
                ],
                "El 20 % de 150 es 150 × 20 ÷ 100 = 30.",
                "Una camiseta cuesta 200 pesos y tiene 10 % de descuento. ¿Cuánto se descuenta?",
                "200 ÷ 10 = 20 pesos de descuento (pagarías 180).",
                [
                    ("¿Cuánto es el 50 % de 80?", ["30", "40", "50"], 1),
                    ("¿Cuánto es el 10 % de 300?", ["30", "3", "100"], 0),
                ],
            ),
            tema(
                "Perímetro y área",
                "El perímetro es la longitud del contorno de una figura. El área es la superficie que ocupa por dentro.",
                [
                    "Perímetro de un rectángulo: 2 × (largo + ancho).",
                    "Área de un rectángulo: largo × ancho.",
                    "El perímetro se mide en unidades (cm); el área, en unidades cuadradas (cm²).",
                ],
                "Un rectángulo de 5 cm por 3 cm tiene perímetro 2 × (5 + 3) = 16 cm y área 5 × 3 = 15 cm².",
                "Un rectángulo mide 7 m de largo y 4 m de ancho. ¿Cuál es su área?",
                "7 × 4 = 28 m².",
                [
                    ("Un cuadrado mide 6 cm por lado. ¿Cuál es su área?",
                     ["24 cm²", "36 cm²", "12 cm²"], 1),
                    ("¿Cuál es el perímetro de un rectángulo de 10 cm por 2 cm?",
                     ["20 cm", "24 cm", "12 cm"], 1),
                ],
            ),
            tema(
                "Ecuaciones sencillas",
                "Una ecuación es una igualdad con un valor desconocido, normalmente x. Resolverla es encontrar el valor de x que hace cierta la igualdad.",
                [
                    "Lo que haces de un lado de la igualdad debes hacerlo del otro.",
                    "Para quitar una suma, resta; para quitar una multiplicación, divide.",
                    "Comprueba sustituyendo el valor en la ecuación original.",
                ],
                "x + 5 = 12 → x = 12 − 5 → x = 7. Comprobación: 7 + 5 = 12.",
                "Resuelve: 3x = 21.",
                "x = 21 ÷ 3 = 7.",
                [
                    ("Resuelve: x + 9 = 15", ["x = 6", "x = 24", "x = 5"], 0),
                    ("Resuelve: 4x = 20", ["x = 16", "x = 80", "x = 5"], 2),
                ],
            ),
            tema(
                "Promedio",
                "El promedio (o media) resume un conjunto de datos: se suman todos los datos y el resultado se divide entre cuántos datos hay.",
                [
                    "Paso 1: suma todos los datos.",
                    "Paso 2: divide la suma entre la cantidad de datos.",
                    "El promedio suele quedar entre el dato menor y el mayor.",
                ],
                "Calificaciones 8, 9 y 10: (8 + 9 + 10) ÷ 3 = 27 ÷ 3 = 9.",
                "Calcula el promedio de 6, 7, 8 y 7.",
                "6 + 7 + 8 + 7 = 28, y 28 ÷ 4 = 7.",
                [
                    ("¿Cuál es el promedio de 4 y 10?", ["6", "7", "14"], 1),
                    ("Para el promedio de 5 datos, ¿entre cuánto divides la suma?",
                     ["Entre 2", "Entre 5", "Entre 10"], 1),
                ],
            ),
        ],
    },
    "espanol": {
        "nombre": "Español",
        "temas": [
            tema(
                "Sustantivos",
                "El sustantivo es la palabra que nombra personas, animales, cosas, lugares o ideas.",
                [
                    "Comunes: nombran de forma general (niño, ciudad).",
                    "Propios: nombran algo en particular y llevan mayúscula (María, México).",
                    "Tienen género (masculino o femenino) y número (singular o plural).",
                ],
                "En «La maestra lee un libro», los sustantivos son maestra y libro.",
                "Encuentra los sustantivos: «El perro de Luis corre por el parque».",
                "perro, Luis, parque.",
                [
                    ("¿Cuál es un sustantivo propio?", ["ciudad", "Guadalajara", "bonita"], 1),
                    ("¿Cuál es un sustantivo?", ["saltar", "azul", "mesa"], 2),
                ],
            ),
            tema(
                "Adjetivos",
                "El adjetivo es la palabra que acompaña al sustantivo para decir cómo es o darle una característica.",
                [
                    "Concuerda con el sustantivo en género y número.",
                    "Responde a la pregunta ¿cómo es?",
                    "Puede ir antes o después del sustantivo.",
                ],
                "En «una casa grande y blanca», grande y blanca son adjetivos.",
                "Encuentra el adjetivo: «El gato negro duerme».",
                "negro.",
                [
                    ("¿Cuál es el adjetivo en «La flor amarilla»?", ["flor", "amarilla", "La"], 1),
                    ("¿Qué adjetivo concuerda con «niñas»?", ["pequeño", "pequeñas", "pequeña"], 1),
                ],
            ),
            tema(
                "Verbos",
                "El verbo es la palabra que expresa acciones, estados o procesos, e indica el tiempo en que ocurren.",
                [
                    "Los infinitivos terminan en -ar, -er o -ir (cantar, comer, vivir).",
                    "Los tiempos básicos son pasado, presente y futuro.",
                    "Cambia según la persona: yo canto, tú cantas.",
                ],
                "Ayer comí (pasado), hoy como (presente), mañana comeré (futuro).",
                "¿En qué tiempo está «jugaremos»?",
                "En futuro.",
                [
                    ("¿Cuál es un verbo?", ["correr", "rápido", "casa"], 0),
                    ("«Cantó» está en tiempo...", ["Presente", "Pasado", "Futuro"], 1),
                ],
            ),
            tema(
                "Sílabas y acentuación",
                "Las palabras se dividen en sílabas. Según cuál sílaba se pronuncia con más fuerza, son agudas, graves o esdrújulas.",
                [
                    "Agudas: la fuerza está en la última sílaba (can-ción).",
                    "Graves: la fuerza está en la penúltima sílaba (ca-sa, ár-bol).",
                    "Esdrújulas: la fuerza está en la antepenúltima sílaba y siempre llevan tilde (mú-si-ca).",
                ],
                "La palabra «teléfono» se divide te-lé-fo-no y es esdrújula.",
                "¿Cuántas sílabas tiene «mariposa»?",
                "Cuatro: ma-ri-po-sa.",
                [
                    ("¿Cuántas sílabas tiene «pelota»?", ["2", "3", "4"], 1),
                    ("«Música» es una palabra...", ["Aguda", "Grave", "Esdrújula"], 2),
                ],
            ),
            tema(
                "Signos de puntuación",
                "Los signos de puntuación organizan el texto y ayudan a leerlo y entenderlo.",
                [
                    "El punto (.) termina una oración.",
                    "La coma (,) separa elementos de una lista o marca una pausa breve.",
                    "En español, las preguntas y exclamaciones llevan signo de apertura y de cierre: ¿...? ¡...!",
                ],
                "Compré manzanas, peras y uvas. ¿Quieres probar?",
                "Coloca los signos que faltan: «Cómo te llamas».",
                "¿Cómo te llamas?",
                [
                    ("¿Qué signo abre una pregunta en español?", ["?", "¿", "¡"], 1),
                    ("¿Qué oración usa bien la coma?",
                     ["Compré pan, leche y huevos.", "Compré, pan leche y huevos.",
                      "Compré pan leche, y huevos."], 0),
                ],
            ),
            tema(
                "Sinónimos y antónimos",
                "Los sinónimos son palabras con significado parecido. Los antónimos son palabras con significado contrario.",
                [
                    "Sinónimos: grande y enorme; bonito y hermoso.",
                    "Antónimos: grande y pequeño; subir y bajar.",
                    "Usar sinónimos ayuda a no repetir palabras al escribir.",
                ],
                "«El día estaba caluroso» puede decirse «El día estaba cálido»; lo contrario sería «frío».",
                "Escribe un antónimo de «alegre».",
                "Triste (también sirve «apenado»).",
                [
                    ("¿Cuál es sinónimo de «rápido»?", ["lento", "veloz", "pesado"], 1),
                    ("¿Cuál es antónimo de «subir»?", ["bajar", "trepar", "elevar"], 0),
                ],
            ),
            tema(
                "La oración: sujeto y predicado",
                "Una oración expresa una idea completa. Se divide en sujeto (de quién se habla) y predicado (lo que se dice del sujeto).",
                [
                    "El sujeto responde a la pregunta ¿quién?",
                    "El predicado contiene el verbo.",
                    "A veces el sujeto no se escribe: en «Corremos», el sujeto es «nosotros».",
                ],
                "«Mi hermana | canta en el coro». Sujeto: Mi hermana. Predicado: canta en el coro.",
                "Señala el sujeto: «Los niños juegan en el patio».",
                "Los niños.",
                [
                    ("En «El perro ladra», ¿cuál es el predicado?", ["El perro", "ladra", "El"], 1),
                    ("¿Qué pregunta ayuda a encontrar el sujeto?",
                     ["¿Quién realiza la acción?", "¿Dónde?", "¿Cuándo?"], 0),
                ],
            ),
            tema(
                "Uso de mayúsculas",
                "Las mayúsculas se usan en casos específicos; el resto de las palabras se escribe con minúscula.",
                [
                    "Al empezar un texto y después de un punto.",
                    "En nombres propios de personas, lugares y países (Sofía, Madrid, Perú).",
                    "Los días de la semana y los meses van con minúscula (lunes, abril).",
                ],
                "Ayer fui con Sofía a Madrid. El lunes regresamos.",
                "¿Cómo se escribe correctamente: «hoy es Lunes» u «hoy es lunes»?",
                "«Hoy es lunes.» La primera palabra lleva mayúscula por iniciar la oración, pero «lunes» va con minúscula.",
                [
                    ("¿Qué palabra se escribe con mayúscula inicial?", ["abril", "Perú", "jueves"], 1),
                    ("Los meses del año en español se escriben con...",
                     ["Minúscula", "Mayúscula", "Todo en mayúsculas"], 0),
                ],
            ),
            tema(
                "Tipos de texto",
                "No todos los textos sirven para lo mismo. Según su propósito, pueden ser narrativos, informativos o instructivos.",
                [
                    "Narrativos: cuentan hechos (cuentos, fábulas).",
                    "Informativos: explican datos (noticias, enciclopedias).",
                    "Instructivos: dan pasos para hacer algo (recetas, manuales).",
                ],
                "Una receta de cocina tiene ingredientes y pasos: es un texto instructivo.",
                "¿Qué tipo de texto es una noticia del periódico?",
                "Informativo.",
                [
                    ("Un cuento es un texto...", ["Narrativo", "Instructivo", "Informativo"], 0),
                    ("Un manual para armar un mueble es un texto...",
                     ["Narrativo", "Instructivo", "Poético"], 1),
                ],
            ),
            tema(
                "Idea principal",
                "La idea principal es lo más importante que dice un texto. Las demás ideas son detalles que la apoyan.",
                [
                    "Lee todo el texto y pregúntate: ¿de qué trata?",
                    "Los detalles dan ejemplos o explican la idea principal.",
                    "Puedes resumirla en una sola oración.",
                ],
                "«Las abejas fabrican miel y ayudan a las plantas a crecer». Idea principal: las abejas son útiles.",
                "Lee: «Las abejas fabrican miel. También polinizan las flores y así ayudan a que crezcan frutas». ¿Cuál es la idea principal?",
                "Las abejas son importantes porque fabrican miel y ayudan a que crezcan las plantas.",
                [
                    ("La idea principal de un texto es...",
                     ["El detalle más pequeño", "Lo más importante que dice el texto",
                      "El nombre del autor"], 1),
                    ("Para encontrar la idea principal conviene...",
                     ["Leer todo el texto y preguntarse de qué trata", "Leer solo la última palabra",
                      "Contar las líneas"], 0),
                ],
            ),
        ],
    },
}


# ---------------------------------------------------------------
# JUEGO DE MEMORIA: cada pareja es (pregunta, respuesta).
# Las claves deben coincidir con las de MATERIAS.
# ---------------------------------------------------------------
PAREJAS = {
    "matematicas": [
        ("7 × 8", "56"), ("9 × 6", "54"), ("12 ÷ 4", "3"),
        ("15 + 27", "42"), ("50 % de 80", "40"), ("1/2 + 1/2", "1"),
    ],
    "espanol": [
        ("Sustantivo", "mesa"), ("Verbo", "correr"), ("Adjetivo", "amarillo"),
        ("Antónimo de alto", "bajo"), ("Sinónimo de rápido", "veloz"),
        ("Palabra aguda", "canción"),
    ],
}

CORREO_VALIDO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------
# BASE DE DATOS
# ---------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def cerrar_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre        TEXT    NOT NULL,
                correo        TEXT    NOT NULL UNIQUE,
                edad          INTEGER NOT NULL,
                especialidad  TEXT    NOT NULL,
                clave_hash    TEXT    NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS resultados (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
                materia     TEXT    NOT NULL,
                tema        INTEGER NOT NULL,
                aciertos    INTEGER NOT NULL,
                total       INTEGER NOT NULL,
                fecha       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


# ---------------------------------------------------------------
# AYUDAS
# ---------------------------------------------------------------
def login_requerido(vista_funcion):
    @wraps(vista_funcion)
    def envoltura(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Inicia sesión para continuar.", "error")
            return redirect(url_for("login"))
        return vista_funcion(*args, **kwargs)
    return envoltura


def render(vista, **contexto):
    """Todas las rutas usan el mismo index.html y cambian con 'vista'."""
    return render_template("index.html", vista=vista, **contexto)


# ---------------------------------------------------------------
# RUTAS
# ---------------------------------------------------------------
@app.route("/")
def inicio():
    if "usuario_id" in session:
        return redirect(url_for("bienvenida"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        clave = request.form.get("clave", "")

        usuario = get_db().execute(
            "SELECT * FROM usuarios WHERE correo = ?", (correo,)
        ).fetchone()

        if usuario and check_password_hash(usuario["clave_hash"], clave):
            session.clear()
            session["usuario_id"] = usuario["id"]
            session["nombre"] = usuario["nombre"]
            return redirect(url_for("bienvenida"))

        flash("Correo o contraseña incorrectos.", "error")
        return render("login", correo=correo)

    return render("login", correo="")


@app.route("/registro", methods=["GET", "POST"])
def registro():
    datos = {"nombre": "", "correo": "", "edad": "", "especialidad": ""}

    if request.method == "POST":
        datos["nombre"] = request.form.get("nombre", "").strip()
        datos["correo"] = request.form.get("correo", "").strip().lower()
        datos["edad"] = request.form.get("edad", "").strip()
        datos["especialidad"] = request.form.get("especialidad", "").strip()
        clave = request.form.get("clave", "")

        errores = []
        if not datos["nombre"]:
            errores.append("Escribe tu nombre completo.")
        if not CORREO_VALIDO.match(datos["correo"]):
            errores.append("Escribe un correo electrónico válido.")
        if not datos["edad"].isdigit() or not (5 <= int(datos["edad"]) <= 120):
            errores.append("La edad debe ser un número entre 5 y 120.")
        if not datos["especialidad"]:
            errores.append("Escribe tu especialidad.")
        if len(clave) < 6:
            errores.append("La contraseña debe tener al menos 6 caracteres.")

        if errores:
            for e in errores:
                flash(e, "error")
            return render("registro", **datos)

        try:
            db = get_db()
            db.execute(
                "INSERT INTO usuarios (nombre, correo, edad, especialidad, clave_hash) "
                "VALUES (?, ?, ?, ?, ?)",
                (datos["nombre"], datos["correo"], int(datos["edad"]),
                 datos["especialidad"], generate_password_hash(clave)),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("Ese correo ya está registrado.", "error")
            return render("registro", **datos)

        flash("¡Registro exitoso! Ahora inicia sesión.", "exito")
        return redirect(url_for("login"))

    return render("registro", **datos)


@app.route("/bienvenida")
@login_requerido
def bienvenida():
    return render("bienvenida")


@app.route("/materias")
@login_requerido
def materias():
    return render("materias", materias=MATERIAS)


@app.route("/materias/<clave>")
@login_requerido
def materia(clave):
    if clave not in MATERIAS:
        abort(404)
    return render("materia", clave=clave, materia=MATERIAS[clave])


@app.route("/materias/<clave>/<int:numero>", endpoint="tema")
@login_requerido
def tema_vista(clave, numero):
    if clave not in MATERIAS:
        abort(404)
    temas = MATERIAS[clave]["temas"]
    if not (1 <= numero <= len(temas)):
        abort(404)
    return render("tema", clave=clave, materia=MATERIAS[clave],
                  numero=numero, total=len(temas), tema=temas[numero - 1])


@app.route("/juegos")
@login_requerido
def juegos():
    return render("juegos", parejas=PAREJAS, materias=MATERIAS)


# Mejor resultado de cada usuario en cada tema.
MEJORES = """
    SELECT usuario_id, materia, tema, MAX(aciertos * 100.0 / total) AS mejor
    FROM resultados
    GROUP BY usuario_id, materia, tema
"""


@app.route("/api/resultado", methods=["POST"])
@login_requerido
def guardar_resultado():
    datos = request.get_json(silent=True) or {}
    clave = datos.get("materia")
    numero = datos.get("tema")
    aciertos = datos.get("aciertos")

    if not isinstance(clave, str) or clave not in MATERIAS:
        return jsonify(ok=False), 400
    if type(numero) is not int or type(aciertos) is not int:
        return jsonify(ok=False), 400

    temas = MATERIAS[clave]["temas"]
    if not (1 <= numero <= len(temas)):
        return jsonify(ok=False), 400

    total = len(temas[numero - 1]["quiz"])
    if total == 0 or not (0 <= aciertos <= total):
        return jsonify(ok=False), 400

    db = get_db()
    db.execute(
        "INSERT INTO resultados (usuario_id, materia, tema, aciertos, total) "
        "VALUES (?, ?, ?, ?, ?)",
        (session["usuario_id"], clave, numero, aciertos, total),
    )
    db.commit()
    return jsonify(ok=True)


@app.route("/progreso")
@login_requerido
def progreso():
    db = get_db()
    uid = session["usuario_id"]

    mios = {
        (r["materia"], r["tema"]): r["mejor"]
        for r in db.execute(
            "SELECT materia, tema, MAX(aciertos * 100.0 / total) AS mejor "
            "FROM resultados WHERE usuario_id = ? GROUP BY materia, tema", (uid,))
    }
    grupo = {
        r["materia"]: r["prom"]
        for r in db.execute(
            "SELECT materia, AVG(mejor) AS prom FROM (" + MEJORES + ") GROUP BY materia")
    }

    tabla, mi_prom = {}, {}
    for clave, m in MATERIAS.items():
        filas = [
            {"numero": n, "titulo": t["titulo"], "mejor": mios.get((clave, n))}
            for n, t in enumerate(m["temas"], start=1)
        ]
        hechos = [f["mejor"] for f in filas if f["mejor"] is not None]
        tabla[clave] = filas
        mi_prom[clave] = sum(hechos) / len(hechos) if hechos else None

    ranking = [
        {"nombre": r["nombre"].split()[0], "temas": r["temas"], "prom": r["prom"]}
        for r in db.execute(
            "SELECT u.nombre AS nombre, COUNT(*) AS temas, AVG(b.mejor) AS prom "
            "FROM (" + MEJORES + ") b JOIN usuarios u ON u.id = b.usuario_id "
            "GROUP BY u.id ORDER BY prom DESC, temas DESC LIMIT 10")
    ]

    return render("progreso", materias=MATERIAS, tabla=tabla, mi_prom=mi_prom,
                  grupo={c: grupo.get(c) for c in MATERIAS}, ranking=ranking)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.errorhandler(404)
def no_encontrado(_error):
    return render("error404"), 404


# Crea la base de datos si no existe (también cuando se usa "flask run").
init_db()

if __name__ == "__main__":
 app.run(debug=True)