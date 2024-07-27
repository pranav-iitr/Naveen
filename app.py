from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

UPLOAD_FOLDER = 'Upload_files'
ALLOWED_EXTENSIONS = {'xlsx'}
DATASET_FOLDER = os.path.join(UPLOAD_FOLDER, 'DATASET')
BANK_FOLDER = os.path.join(UPLOAD_FOLDER, 'Bank')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to load all specified Excel files in the directory
def load_excel_files(directory):
    data_frames = []
    for root, dirs, files in os.walk(directory):
        for file_name in files:
            if file_name.endswith('.xlsx'):
                file_path = os.path.join(root, file_name)
                bank_name = os.path.basename(os.path.dirname(file_path))
                product_type = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
                try:
                    xls = pd.ExcelFile(file_path)
                    for sheet_name in xls.sheet_names:
                        df = pd.read_excel(xls, sheet_name)
                        data_frames.append((df, sheet_name, file_name, bank_name, product_type))
                        print(f"Loaded file: {file_path}, Sheet: {sheet_name}")
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")
    return data_frames

# Function to clean DataFrame columns
def clean_columns(df):
    return df.apply(lambda col: col.map(lambda x: x.strip().lower() if isinstance(x, str) else x))

# Function to search for the value in all columns across all loaded dataframes
def search_value_in_all_columns(data_frames, search_value):
    search_value = str(search_value).strip().lower()
    results = []
    all_rows = pd.DataFrame()

    for df, sheet_name, file_name, bank_name, product_type in data_frames:
        df_cleaned = clean_columns(df)
        for column in df_cleaned.columns:
            matching_rows = df_cleaned[df_cleaned[column].astype(str).str.contains(search_value, na=False)]
            if not matching_rows.empty:
                matching_rows['Sheet'] = sheet_name
                matching_rows['File'] = file_name
                matching_rows['Source_Column'] = column
                matching_rows['Bank_Name'] = bank_name if bank_name != 'Bank' else ''
                matching_rows['Product_Type'] = product_type if product_type != 'Bank' else ''
                all_rows = pd.concat([all_rows, matching_rows])

    distinct_rows = all_rows.drop_duplicates(subset=all_rows.columns.difference(['Sheet', 'File', 'Source_Column', 'Bank_Name', 'Product_Type']))

    for _, row in distinct_rows.iterrows():
        result = {
            'Sheet': row['Sheet'],
            'File': row['File'],
            'Source_Column': row['Source_Column'],
            'Bank_Name': row['Bank_Name'],
            'Product_Type': row['Product_Type'],
            'Data': row.drop(['Sheet', 'File', 'Source_Column', 'Bank_Name', 'Product_Type']).to_dict()
        }
        results.append(result)

    total_distinct_count = len(distinct_rows)

    return results, total_distinct_count

# Function to get unique bank names and product types
def get_bank_and_product_types():
    bank_names = set()
    product_types = set()
    for root, dirs, files in os.walk(BANK_FOLDER):
        for dir_name in dirs:
            if os.path.basename(root) == 'Bank':
                bank_names.add(dir_name)
            else:
                product_types.add(dir_name)
    return list(bank_names), list(product_types)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    bank_name = request.form.get('bank_name', '').strip()
    product_type = request.form.get('product_type', '').strip()

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = file.filename
        if bank_name and product_type:
            dir_path = os.path.join(BANK_FOLDER, bank_name, product_type)
        elif bank_name:
            dir_path = os.path.join(BANK_FOLDER, bank_name)
        else:
            dir_path = DATASET_FOLDER

        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, filename)
        file.save(file_path)
        
        # Add bank name and product type to dropdown list
        if bank_name and bank_name not in get_bank_and_product_types()[0]:
            os.makedirs(os.path.join(BANK_FOLDER, bank_name), exist_ok=True)
        if product_type and product_type not in get_bank_and_product_types()[1]:
            os.makedirs(os.path.join(BANK_FOLDER, bank_name, product_type), exist_ok=True)
            
        return jsonify({'message': 'File uploaded successfully', 'filename': filename})
    else:
        return jsonify({'error': 'Invalid file type, only .xlsx files are allowed'}), 400

@app.route('/search', methods=['POST'])
def search():

    data = request.get_json()

    

    if not data:
        return jsonify({'error': 'Invalid JSON payload'}), 400
    
    search_value = data.get('search_value')
    bank_name = data.get('bank_name', '').strip()
    product_type = data.get('product_type', '').strip()
    if not search_value:
        return jsonify({'error': 'search_value is required field'}), 400

    directory = DATASET_FOLDER if not bank_name else os.path.join(BANK_FOLDER, bank_name, product_type) if product_type else os.path.join(BANK_FOLDER, bank_name)
    data_frames = load_excel_files(UPLOAD_FOLDER if not bank_name and not product_type else directory)

    results, total_distinct_count = search_value_in_all_columns(data_frames, search_value)

    response = jsonify({'results': results, 'total_distinct_count': total_distinct_count})
    response.headers.set('Content-Type', 'application/json')
    return response

@app.route('/api/dropdowns', methods=['GET'])
def get_dropdowns():
    bank_names, product_types = get_bank_and_product_types()
    return jsonify({'bank_names': bank_names, 'product_types': product_types})

if __name__ == '__main__':
    app.run(port=5500, host='0.0.0.0', debug=True)
