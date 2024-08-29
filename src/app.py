from flask import Flask, render_template, request, send_file, jsonify
import io
import zipfile
import fitz  # PyMuPDF
from PIL import Image
import re

app = Flask(__name__)

left_side_threshold = 3 * 72 / 2.54  # 3 cm converted to points
question_start_points = []  # List to hold question start points (x0, y0 coordinates)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['pdf']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and file.filename.endswith('.pdf'):
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")

        question_positions = []
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            text = page.get_text()

            for match in re.finditer(r'(\d+)\)', text):
                bboxes = page.search_for(match.group(0))

                if bboxes:
                    bbox = bboxes[0]

                    if bbox[0] < left_side_threshold:
                        question_positions.append((page_num, bbox))
                        print(bbox)

        question_end_points = [item for item in question_start_points for _ in range(2)]
        # Print the extracted question positions (for debugging or inspection)
        # print("Extracted question positions:")
        # for pos in question_positions:
        #     print(f'Page {pos[0]}: {pos[1]}')

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # Crop images based on question positions
                for i in range(len(question_positions)):
                    if question_positions[i][0] == page_num:
                        bbox = question_positions[i][1]

                        # Skip storing the first question's start point
                        if i > 0:
                            # Only store start points for questions after the first one
                            start_point = (bbox[0], bbox[1])
                            question_start_points.append((page_num, start_point))

                        # Adjust crop box if needed (e.g., add padding)
                        crop_box = (0 - 2 * 72 / 2.54, bbox[1], pix.width - 1 * 72 / 2.54, bbox[1]+2 * 72 / 2.54)
                        cropped_img = img.crop(crop_box)

                        # Save cropped image to a BytesIO buffer
                        img_buffer = io.BytesIO()
                        cropped_img.save(img_buffer, format='PNG')
                        img_buffer.seek(0)

                        # Add the cropped image to the zip file
                        zip_file.writestr(f'page_{page_num + 1}_question_{i + 1}.png', img_buffer.getvalue())

        # Example: Printing the start points of all questions
        # for page, start_point in question_start_points:
        #     print(f"Question on page {page + 1} starts at position {start_point}")

        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name='cropped_pages.zip',
            mimetype='application/zip'
        )

    return jsonify({'error': 'Invalid file format'}), 400

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8000)
