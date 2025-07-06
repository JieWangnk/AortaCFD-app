import os
from flask import Flask, render_template, request, abort, redirect, url_for, flash
from markupsafe import Markup
import markdown
import math
import subprocess
from werkzeug.utils import secure_filename

app = Flask(__name__)

DOCS_PATH = os.path.join(os.path.dirname(__file__), 'docs')

app.config['UPLOAD_FOLDER'] = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/CAD'))
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB max file size
app.secret_key = 'your_secret_key'  # Needed for flash messages

ALLOWED_EXTENSIONS = {'stl', 'csv', 'json'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/physics', methods=['GET', 'POST'])
def physics():
    reynolds = None
    womersley = None
    error = None
    cardiac_cycle = None
    angular_freq = None
    kinematic_visc = None
    if request.method == 'POST':
        try:
            diameter = float(request.form['diameter'])
            velocity = float(request.form['velocity'])
            viscosity = float(request.form['viscosity']) if request.form.get('viscosity') else 0.0035
            density = float(request.form['density']) if request.form.get('density') else 1060
            heart_rate = float(request.form['heart_rate']) if request.form.get('heart_rate') else 75
            # Cardiac cycle (T)
            cardiac_cycle = 60.0 / heart_rate if heart_rate else None
            # Angular frequency (omega)
            angular_freq = 2 * math.pi / cardiac_cycle if cardiac_cycle else None
            # Kinematic viscosity (nu)
            kinematic_visc = viscosity / density if density else None
            # Reynolds number
            rho = density
            mu = viscosity
            reynolds = (rho * velocity * diameter) / mu
            # Womersley number
            if diameter and angular_freq and kinematic_visc:
                womersley = (diameter / 2.0) * math.sqrt(angular_freq / kinematic_visc)
        except Exception as e:
            error = str(e)
    return render_template('physics.html', reynolds=reynolds, womersley=womersley, error=error,
                           cardiac_cycle=cardiac_cycle, angular_freq=angular_freq, kinematic_visc=kinematic_visc)

@app.route('/docs/<docname>')
def docs_dynamic(docname):
    md_path = os.path.join(DOCS_PATH, f"{docname}.md")
    if not os.path.exists(md_path):
        abort(404)
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    html_content = markdown.markdown(md_content, extensions=['fenced_code', 'tables'])
    return render_template('docs_dynamic.html', content=Markup(html_content), docname=docname)

@app.route('/docs/getting_started')
def docs_getting_started():
    # This would normally parse the markdown, but for now, we use a static HTML template
    return render_template('docs_getting_started.html')

@app.route('/docs/features')
def docs_features():
    return render_template('docs_features.html')

@app.route('/docs/installation')
def docs_installation():
    return render_template('docs_installation.html')

@app.route('/docs/command_reference')
def docs_command_reference():
    return render_template('docs_command_reference.html')

@app.route('/docs/input_data_structure')
def docs_input_data_structure():
    return render_template('docs_input_data_structure.html')

@app.route('/docs/known_issues')
def docs_known_issues():
    return render_template('docs_known_issues.html')

@app.route('/docs/updates_roadmap')
def docs_updates_roadmap():
    return render_template('docs_updates_roadmap.html')

@app.route('/docs/contributing')
def docs_contributing():
    return render_template('docs_contributing.html')

@app.route('/docs/license')
def docs_license():
    return render_template('docs_license.html')

@app.route('/3ewk')
def three_ewk_demo():
    """3-Element Windkessel interactive demo page"""
    return render_template('3ewk_interactive_demo.html')

@app.route('/3ewk/methodology')
def three_ewk_methodology():
    """3-Element Windkessel full methodology documentation"""
    return docs_dynamic('3ewk_methodology')

@app.route('/roadmap')
def development_roadmap():
    """Development roadmap and project status"""
    return docs_dynamic('development_roadmap')

@app.route('/run_sim', methods=['GET', 'POST'])
def run_sim():
    sim_output = None
    sim_error = None
    if request.method == 'POST':
        case = request.form.get('case')
        profile = request.form.get('profile')
        if case and profile:
            cmd = [
                'bash', '-c',
                'source /opt/openfoam8/etc/bashrc && cd /home/mchi4jw4/GitHub/AortaCFD-app && python app.py runAll --case {} --profile {}'.format(case, profile)
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
                sim_output = result.stdout
                sim_error = result.stderr
            except Exception as e:
                sim_error = str(e)
    return render_template('run_sim.html', sim_output=sim_output, sim_error=sim_error)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    message = None
    if request.method == 'POST':
        case_folder = request.form.get('case_folder', '').strip()
        if 'file' not in request.files or not case_folder:
            message = 'No file or case folder specified.'
        else:
            files = request.files.getlist('file')
            uploaded_files = []
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    case_path = os.path.join(app.config['UPLOAD_FOLDER'], case_folder)
                    os.makedirs(case_path, exist_ok=True)
                    save_path = os.path.join(case_path, filename)
                    # Prevent overwriting: add a suffix if file exists
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(save_path):
                        filename = f"{base}_{counter}{ext}"
                        save_path = os.path.join(case_path, filename)
                        counter += 1
                    file.save(save_path)
                    uploaded_files.append(filename)
            if uploaded_files:
                message = f"Uploaded: {', '.join(uploaded_files)} to {case_folder}!"
            else:
                message = 'No valid files uploaded.'
    return render_template('upload.html', message=message)

if __name__ == '__main__':
    app.run(debug=True) 