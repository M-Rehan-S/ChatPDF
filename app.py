from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFaceEndpoint, ChatHuggingFace
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
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    model_kwargs={'device': 'cpu'}
)

VectorStore = None
upload_folder = "uploads"
os.makedirs(upload_folder, exist_ok=True)

# raw_llm = HuggingFaceEndpoint(
#             repo_id="mistralai/Mistral-7B-Instruct-v0.3",
#             max_new_tokens=500,
#             task = 'conversational',
#             temperature=0.1,
#         )

llm = HuggingFaceEndpoint(
    repo_id="meta-llama/Meta-Llama-3-8B-Instruct",
    max_new_tokens=500,
    temperature=0.1,
)

hf_client = InferenceClient(
    model="meta-llama/Meta-Llama-3-8B-Instruct", # Or "mistralai/Mistral-7B-Instruct-v0.3"
    token=os.getenv("HF_TOKEN")
)

system_prompt = (
    "You are a helpful assistant. Use the following context to answer the question. "
    "If the answer is not in the context, say 'I cannot find that in the document.' "
    "Do not make things up.\n\n"
    "Context:\n{context}"
)

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}"),
])

question_answer_chain = create_stuff_documents_chain(llm, prompt)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_pdf():   
    global VectorStore
    
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    # ─── FIX 2: KEEP VARIABLES SCOPED TO THE INCOMING FILE ───
    # These represent only the current file being added to your existing accumulated database.
    current_file_chunks = []
    filename = file.filename
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)

    try:
        # Load and parse the new incoming PDF
        loader = PyPDFLoader(filepath)
        docs = loader.load()
        pages_count = len(docs)
        
        # Split the new document into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
        chunks = text_splitter.split_documents(docs)
        chunks_count = len(chunks)
        
        current_file_chunks.extend(chunks)
        
    except Exception as e:
        # Clean up the file if parsing fails so your disk stays clean
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"error": f"Failed to parse {filename}: {str(e)}"}), 500

    if not current_file_chunks:
        return jsonify({"error": f"No text could be extracted from {filename}"}), 400

    try:
        # ─── THE VECTORSTORE GROWS ACCUMULATIVELY ───
        if VectorStore is None:
            # First time upload: Create the Chroma instance
            VectorStore = Chroma.from_documents(current_file_chunks, embeddings)
        else:
            # Subsequent uploads: Append new chunks without overwriting old ones
            VectorStore.add_documents(current_file_chunks)

        # Return accurate data representing the specific file that was just loaded
        return jsonify({
            "message": f"Successfully added '{filename}' to the knowledge base!",
            'name': filename,
            'pages': pages_count,
            'chunks': chunks_count
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

@app.route("/chat", methods=["POST"])
def chat():
    global VectorStore
    if VectorStore is None:
        return jsonify({"error": "Knowledge base is empty. Please upload PDFs first."}), 400

    data = request.json or {}
    user_query = data.get("query")
    
    # Dynamic 'k' selection: Default to 3 chunks if the user doesn't pass a value
    k_chunks = data.get("top_k", 3) 

    if not user_query:
        return jsonify({"error": "No query provided"}), 400

    try:
        # Generate a dynamic retriever matching the user's specific chunk requirement
        retriever = VectorStore.as_retriever(search_kwargs={"k": int(k_chunks)})
        retrieved_docs = retriever.invoke(user_query)
        context = "\n\n".join([doc.page_content for doc in retrieved_docs])

        # rag_chain = create_retrieval_chain(retriever, question_answer_chain)

        response = hf_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt.format(context=context)},
                {"role": "user", "content": user_query}
            ],
            max_tokens=500,
            temperature=0.1
        )
        # response = rag_chain.invoke({"input": user_query})
        
        formatted_sources = [
            {
                "doc_name": os.path.basename(doc.metadata.get("source", "Unknown")),
                "page": doc.metadata.get("page", 0) + 1
            }
            for doc in retrieved_docs
        ]
        return jsonify({
            "answer": response.choices[0].message.content,
            "sources": formatted_sources
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)