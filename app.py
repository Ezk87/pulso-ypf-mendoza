# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, redirect, url_for
import csv, os, datetime, statistics

app = Flask(__name__)

# --- CONFIGURACIÓN ---
STATIONS = ["A", "B", "C"]  # editar si agregan más
SHIFTS = ["Mañana", "Tarde", "Noche"]
TENURES = ["0–6m", "6–24m", "2–5a", "5+a"]
MIN_GROUP_SIZE = 5  # no mostrar métricas si n < 5

QUESTIONS = [
    "¿Sentís que los turnos y horarios se están asignando de manera justa?",
    "¿La carga de trabajo en tu turno te parece razonable?",
    "¿Te sentís seguro/a trabajando en tu turno actual?",
    "Si alguna vez trabajás turno noche: ¿sentís que hay suficiente seguridad para trabajar tranquilo/a?",
    "¿Sentís que tenés oportunidades claras para ganar incentivos o extras?"
]

DATA_DIR = os.environ.get("DATA_DIR", ".")   # por defecto, carpeta actual
CSV_FILE = os.path.join(DATA_DIR, "respuestas.csv")


HTML_FORM = """
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pulso YPF Mendoza</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 760px; margin: 20px auto; }
  h1, h2 { margin: 0.3em 0; }
  .card { border: 1px solid #ddd; border-radius: 10px; padding: 18px; margin-bottom: 16px; }
  label { font-weight: bold; }
  select, textarea, input[type=number] { width: 100%; padding: 8px; margin-top: 6px; }
  button { padding: 10px 16px; border: 0; border-radius: 8px; cursor: pointer; }
  .primary { background: #1f7ae0; color: #fff; }
  .muted { color: #666; font-size: 12px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .full { grid-column: 1 / -1; }
</style>
</head>
<body>
  <h1>Encuesta Anónima – Pulso YPF Mendoza</h1>
  <div class="card">
    <p>Tu voz ayuda a mejorar la seguridad, la formación y el ambiente de trabajo. <b>Es 100% anónimo</b>. No recolectamos nombre, email ni IP.</p>
    <p class="muted">Privacidad: no se publican resultados de grupos con n &lt; {{min_group}}. Tus datos se usan solo para mejora interna.</p>
  </div>
  <form method="post" class="card">
    <div class="grid">
      <div>
        <label>Estación</label>
        <select name="station" required>
          {% for s in stations %}<option value="{{s}}">{{s}}</option>{% endfor %}
        </select>
      </div>
      <div>
        <label>Turno</label>
        <select name="shift" required>
          {% for s in shifts %}<option value="{{s}}">{{s}}</option>{% endfor %}
        </select>
      </div>
      <div>
        <label>Antigüedad</label>
        <select name="tenure" required>
          {% for t in tenures %}<option value="{{t}}">{{t}}</option>{% endfor %}
        </select>
      </div>
      <div>
        <label>¿Qué tan probable es que recomiendes trabajar acá? (0–10)</label>
        <input type="number" name="enps" min="0" max="10" required>
      </div>
    </div>
    <div class="full">
      <p><b>Indicá tu acuerdo (1 = Totalmente en desacuerdo, 5 = Totalmente de acuerdo)</b></p>
      {% for q in questions %}
        <div style="margin:10px 0;">
          <label>{{ loop.index }}) {{ q }}</label>
          <select name="q{{ loop.index0 }}" required>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="4">4</option>
            <option value="5">5</option>
          </select>
        </div>
      {% endfor %}
    </div>
    <div class="full">
      <label>¿Qué está funcionando bien?</label>
      <textarea name="open_good" rows="2"></textarea>
    </div>
    <div class="full">
      <label>¿Qué deberíamos mejorar primero?</label>
      <textarea name="open_better" rows="2"></textarea>
    </div>
    <button type="submit" class="primary">Enviar</button>
  </form>
  <p class="muted">Versión {{version}} · <a href="{{url_for('metodo')}}">Método y Privacidad</a></p>
</body>
</html>
"""

HTML_THANKS = """
<!doctype html><meta charset="utf-8">
<div style="font-family:Arial;max-width:760px;margin:40px auto;">
  <h3>¡Gracias por responder!</h3>
  <p>Tu aporte será parte de las mejoras de los próximos 30 días.</p>
  <a href="/">Volver</a>
</div>
"""

HTML_METODO = """
<!doctype html><meta charset="utf-8">
<div style="font-family:Arial;max-width:760px;margin:40px auto;">
  <h2>Método y Privacidad</h2>
  <ul>
    <li><b>Anonimato real</b>: no se almacenan nombres, emails ni IPs.</li>
    <li><b>Umbral de reporte</b>: no se publican resultados de grupos con n &lt; {{min_group}}.</li>
    <li><b>Uso de datos</b>: exclusivo para mejoras de seguridad, formación y gestión.</li>
    <li><b>Transparencia</b>: se comunicarán “3 cosas que escuchamos” y “3 acciones” cada 30 días.</li>
  </ul>
  <a href="/">Volver</a>
</div>
"""

def ensure_csv_header():
    exists = os.path.exists(CSV_FILE)
    if not exists:
        fields = ["timestamp","station","shift","tenure","enps","open_good","open_better"] + [f"q{i+1}" for i in range(len(QUESTIONS))]
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fields)

@app.route("/", methods=["GET","POST"])
def survey():
    ensure_csv_header()
    if request.method == "POST":
        row = {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "station": request.form["station"],
            "shift": request.form["shift"],
            "tenure": request.form["tenure"],
            "enps": request.form["enps"],
            "open_good": request.form.get("open_good","").strip(),
            "open_better": request.form.get("open_better","").strip()
        }
        for i,_ in enumerate(QUESTIONS):
            row[f"q{i+1}"] = request.form[f"q{i}"]
        write_csv(row)
        return redirect("/gracias")
    return render_template_string(HTML_FORM, questions=QUESTIONS, stations=STATIONS, shifts=SHIFTS, tenures=TENURES, min_group=MIN_GROUP_SIZE, version="1.0")

@app.route("/gracias")
def gracias():
    return HTML_THANKS

@app.route("/metodo")
def metodo():
    return render_template_string(HTML_METODO, min_group=MIN_GROUP_SIZE)

def write_csv(row: dict):
    ensure_csv_header()
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writerow(row)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
