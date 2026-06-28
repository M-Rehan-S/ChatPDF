from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFaceEndpoint
from langchain_community.vectorstores import Chroma
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate


load_dotenv()

def create_app():
    app = Flask(__name__)
    CORS(app)
    os.makedirs('uploads', exist_ok=True)
    return app

app = create_app()
VectorStore = None  
Retriever = None
upload_folder = 'uploads'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_pdf():   
    global VectorStore
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    all_chunks = []
    processed_files = []

    # Initialize the local embedding model
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={'device': 'cpu'}
    )

    # Process every file uploaded in the request
    filepath = os.path.join(upload_folder, file.filename)
    file.save(filepath)
    processed_files.append(file.filename)

    try:
        loader = PyPDFLoader(filepath)
        docs = loader.load()
        pages = len(docs)
        name = file.filename
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
        chunks = text_splitter.split_documents(docs)
        chunksCount = len(chunks)
        all_chunks.extend(chunks)
    except Exception as e:
        return jsonify({"error": f"Failed to parse {file.filename}: {str(e)}"}), 500

    if not all_chunks:
        return jsonify({"error": "No text could be extracted from the uploaded PDFs"}), 400

    try:
        # Multi-File handling: If DB doesn't exist, create it. Otherwise, APPEND to it.
        if VectorStore is None:
            VectorStore = Chroma.from_documents(all_chunks, embeddings)
        else:
            VectorStore.add_documents(all_chunks)

        return jsonify({
            "message": f"Successfully added {len(processed_files)} file(s) to the knowledge base!",
            'name': name,
            'pages': pages,
            'chunks': chunksCount
        }), 200

    except Exception as e:
        return jsonify({"error": f"Vector Store error: {str(e)}"}), 500


@app.route('/delete/<filename>', methods=['DELETE'])
def delete(filename):
    global VectorStore
    
    if VectorStore is None:
        return jsonify({"error": "Knowledge base is empty."}), 400

    try:
        # Reconstruct the exact path string that LangChain generated during upload
        # Example: "uploads/my_lecture_notes.pdf"
        target_source_path = os.path.join(upload_folder, filename)
        
        # Query Chroma directly to remove chunks matching that specific source path
        VectorStore._collection.delete(
            where={"source": target_source_path}
        )
        if os.path.exists(target_source_path):
            os.remove(target_source_path)  # Remove the file from the uploads folder
        else :
            print(f"File not found: {target_source_path}")
            return jsonify({"error": f"File {filename} not found in uploads."}), 404
        return jsonify({
            "message": f"Successfully dropped all embeddings for file: {filename}"
        }), 200

    except Exception as e:
        return jsonify({"error": f"Failed to delete document: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)