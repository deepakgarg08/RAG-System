import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"

BASE_DIR = Path(__file__).resolve().parent.parent

TEMP_DIR = BASE_DIR / "data/synthetic_legal_db/temp_uploads"
PERSISTENT_DIR = BASE_DIR / "data/synthetic_legal_db/persistent_contracts"

results = {
    "mode1": [],
    "mode2": [],
    "mode3": [],
    "stress": []
}


# -------------------------------
# Helper Functions
# -------------------------------

def print_section(title):
    print("\n" + "=" * 60)
    print(f"🔹 {title}")
    print("=" * 60)


def parse_sse(response):
    """Parse Server-Sent Events (SSE) response into plain text."""
    output = ""
    for line in response.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data:"):
                content = decoded.replace("data:", "").strip()
                if content != "[DONE]":
                    output += content + " "
    return output.strip()


# -------------------------------
# TEST FUNCTIONS
# -------------------------------

def run_mode1_test(file_path, question, mode):
    print(f"\n📄 File: {file_path.name}")
    print(f"❓ Question: {question}")

    start = time.time()

    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                f"{BASE_URL}/api/analyze",
                files={"file": f},
                data={"question": question},
                stream=True
            )
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return

    latency = time.time() - start

    if response.status_code != 200:
        print("❌ ERROR:", response.text)
        return

    response_text = parse_sse(response)

    print("🧠 Response:")
    print(response_text[:500])
    print(f"⏱️ Latency: {latency:.2f}s")

    results[mode].append({
        "file": file_path.name,
        "question": question,
        "response": response_text,
        "status_code": response.status_code,
        "latency": latency
    })


def run_mode3_test(question, mode):
    print(f"\n❓ Question: {question}")

    start = time.time()

    try:
        response = requests.post(
            f"{BASE_URL}/api/query",
            json={"question": question},
            stream=True
        )
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return

    latency = time.time() - start

    if response.status_code != 200:
        print("❌ ERROR:", response.text)
        return

    response_text = parse_sse(response)

    print("🧠 Response:")
    print(response_text[:500])
    print(f"⏱️ Latency: {latency:.2f}s")

    results[mode].append({
        "question": question,
        "response": response_text,
        "status_code": response.status_code,
        "latency": latency
    })


def ingest_all():
    print_section("INGESTING PERSISTENT CONTRACTS")

    for file in PERSISTENT_DIR.glob("*.pdf"):
        print(f"📥 Ingesting: {file.name}")

        try:
            with open(file, "rb") as f:
                response = requests.post(
                    f"{BASE_URL}/api/ingest",
                    files={"file": f},
                )
            print(f"Status: {response.status_code}")
        except Exception as e:
            print(f"❌ Failed to ingest {file.name}: {e}")


# -------------------------------
# TEST EXECUTION
# -------------------------------

def run_tests():
    print_section("STARTING RAG SYSTEM TESTS")

    temp_file = TEMP_DIR / "temp_contract_1.pdf"

    if not temp_file.exists():
        print(f"❌ File not found: {temp_file}")
        return

    # -------------------------------
    # MODE 1
    # -------------------------------
    print_section("MODE 1 — Single Document Analysis")

    run_mode1_test(temp_file, "Is this contract GDPR compliant?", "mode1")
    run_mode1_test(temp_file, "Does this contract have unlimited liability?", "mode1")
    run_mode1_test(temp_file, "What kind of termination clause is present?", "mode1")

    # -------------------------------
    # MODE 2
    # -------------------------------
    print_section("MODE 2 — Compare with Database")

    run_mode1_test(temp_file, "Compare this contract with existing contracts", "mode2")
    run_mode1_test(temp_file, "How does this contract differ in terms of termination clauses?", "mode2")
    run_mode1_test(temp_file, "Which contracts are most similar to this one?", "mode2")

    # -------------------------------
    # MODE 3
    # -------------------------------
    print_section("MODE 3 — Query Database")

    run_mode3_test("Which contracts are missing GDPR compliance?", "mode3")
    run_mode3_test("Which contracts have unlimited liability?", "mode3")
    run_mode3_test("Which contracts have weak termination clauses?", "mode3")
    run_mode3_test("Which contracts are GDPR compliant but have weak termination clauses?", "mode3")

    # -------------------------------
    # STRESS TESTS
    # -------------------------------
    print_section("STRESS TESTS")

    run_mode3_test("Do any agreements follow European data protection regulations?", "stress")
    run_mode3_test("Is this contract legally safe?", "stress")


# -------------------------------
# MAIN
# -------------------------------

if __name__ == "__main__":
    ingest_all()
    run_tests()

    output_file = BASE_DIR / "rag_test_results.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    print(f"\n✅ Results saved to: {output_file}")