import os
import json
import requests
import random
import time
import re
import subprocess

# --- Global Configuration ---
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
PLOTS_DIR = './plots'
TEMP_PLOT_SCRIPT = 'temp_plot_script.py'


# --- 1. Helper Function: Load API Key ---
def load_api_key():
    """
    Retrieves the OpenRouter API key from environment variables.
    """
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise ValueError("Error: OPENROUTER_API_KEY environment variable not set.")
    print("✓ API Key loaded successfully.")
    return api_key


# --- 2. Helper Function: Call OpenRouter API ---
def call_openrouter(api_key, model, prompt):
    """
    Sends a request to the OpenRouter API and returns the model's raw response.
    """
    print(f"  > Calling model: {model}...")
    try:
        response = requests.post(
            url=OPENROUTER_API_URL,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            data=json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            }),
            timeout=240  # Increased timeout for more complex generations
        )
        response.raise_for_status()
        response_json = response.json()
        content = response_json['choices'][0]['message']['content']
        return content
    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}")
        raise


# --- Helper Functions for Content Extraction ---
def _extract_code(text, language='python'):
    """Extracts code from a markdown block."""
    # Pattern to find a code block for the given language
    pattern = re.compile(rf'```{language}\n(.*?)\n```', re.DOTALL)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    # Fallback for when the model forgets the language tag
    if text.strip().startswith('```') and text.strip().endswith('```'):
        return text.strip()[3:-3].strip()
    # Fallback if no markdown is used at all
    return text


def _extract_json(text):
    """Extracts a JSON object from a markdown block or raw text."""
    # The JSON is often inside a markdown block
    json_str = _extract_code(text, 'json')
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}. Trying to parse raw text.")
        # If extraction fails, maybe the raw text is the JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print("Could not parse JSON from response.")
            raise


# --- 3. Step 1: Get User Input and Generate Syllabus ---
def get_and_generate_syllabus(api_key):
    """
    Prompts user for topics and uses Perplexity Sonar to generate a syllabus.

    Args:
        api_key (str): The OpenRouter API key.

    Returns:
        tuple: A tuple containing the user's topic list (str) and the syllabus (dict).
    """
    print("\n--- Step 1: Defining Syllabus ---")
    topics_list = input("Enter 1-2 GED Science topics (e.g., 'Genetics and DNA, Chemical Reactions'): ")
    if not topics_list:
        raise ValueError("Topic list cannot be empty.")

    model = 'perplexity/sonar'
    prompt = f"""
    You are an expert curriculum developer for the GED Science test.
    Research the following user-provided topics: "{topics_list}".

    Your task is to break these topics down into 3 to 5 distinct, teachable sub-topics. For each sub-topic, provide a detailed, concise description (2-4 sentences) suitable for a high school student.

    Output your response as a single, valid JSON object inside a JSON markdown block.
    Example Structure:
    ```json
    {{
      "sub_topics": [
        {{ "name": "Sub-topic 1", "description": "Description 1..." }},
        {{ "name": "Sub-topic 2", "description": "Description 2..." }}
      ]
    }}
    ```
    """
    response_content = call_openrouter(api_key, model, prompt)
    syllabus_json = _extract_json(response_content)

    # Basic validation
    if 'sub_topics' not in syllabus_json or not isinstance(syllabus_json['sub_topics'], list):
        raise ValueError("Syllabus JSON is missing 'sub_topics' list.")

    print(f"✓ Syllabus generated for '{topics_list}' with {len(syllabus_json['sub_topics'])} sub-topics.")
    return topics_list, syllabus_json


# --- 4. Step 2: Generate Plots via Executable Python Code ---
def generate_plots(api_key, syllabus_json):
    """
    Uses Gemini to write Python code that generates plots, then executes that code.

    Args:
        api_key (str): The OpenRouter API key.
        syllabus_json (dict): The syllabus data.

    Returns:
        dict: A dictionary containing plot metadata, MCQs, and local file paths.
    """
    print("\n--- Step 2: Generating Plots ---")
    model = 'google/gemini-2.5-pro'
    prompt = f"""
    You are an expert Python programmer specializing in `matplotlib`. Your task is to write a complete, self-contained Python script that generates 2 data plots relevant to the following science syllabus and then prints a JSON object with their metadata.

    **Syllabus for Context:**
    {json.dumps(syllabus_json, indent=2)}

    **Requirements for the Python Script you will write:**
    1.  It must import all necessary libraries (`os`, `matplotlib.pyplot`, `json`, `time`).
    2.  It must create a directory named `./plots` if it doesn't exist.
    3.  It must generate two different plot types from: `bar`, `line`, `scatter`, `pie`.
    4.  For each plot:
        - Generate realistic sample data.
        - Set a clear title and labels.
        - **For pie charts, ensure slice labels are legible by using `textprops={{'color':"black", 'size':'large'}}`.**
        - Save the plot as a PNG file to the `./plots` directory with a unique name (e.g., using `time.time()`).
    5.  After saving the plots, the script must create a list of dictionaries, one for each plot, containing: `path`, a `description` of the plot, and two `mcqs` (multiple-choice questions) based on the plot.
    6.  Finally, the script MUST print this list as a JSON string to standard output. This is the only thing it should print.

    **Example of the Python script you should generate:**
    ```python
    import os
    import matplotlib.pyplot as plt
    import json
    import time

    def generate_all_plots():
        PLOTS_DIR = './plots'
        os.makedirs(PLOTS_DIR, exist_ok=True)

        plot_metadata = []

        # --- Plot 1: Bar Chart ---
        fig1, ax1 = plt.subplots()
        data1 = {{'Group A': 25, 'Group B': 40, 'Group C': 30}}
        ax1.bar(data1.keys(), data1.values())
        ax1.set_title('Example Bar Chart')
        ax1.set_xlabel('Category')
        ax1.set_ylabel('Value')
        path1 = os.path.join(PLOTS_DIR, f"plot_{{int(time.time())}}_1.png")
        plt.savefig(path1)
        plt.close(fig1)

        plot_metadata.append({{
            "path": path1,
            "description": "This bar chart compares the values of three different categories.",
            "mcqs": [
                {{"question": "Which group has the highest value?", "options": ["A", "B", "C"], "answer": "B"}},
                {{"question": "What is the approximate value of Group A?", "options": ["25", "30", "40"], "answer": "25"}}
            ]
        }})

        # --- Plot 2: Pie Chart ---
        fig2, ax2 = plt.subplots()
        data2 = {{'Apples': 45, 'Oranges': 30, 'Bananas': 25}}
        ax2.pie(data2.values(), labels=data2.keys(), autopct='%1.1f%%', textprops={{'color':"black", 'size':'large'}})
        ax2.set_title('Example Pie Chart')
        path2 = os.path.join(PLOTS_DIR, f"plot_{{int(time.time())}}_2.png")
        plt.savefig(path2)
        plt.close(fig2)

        plot_metadata.append({{
            "path": path2,
            "description": "This pie chart shows the percentage distribution of fruits.",
            "mcqs": [
                {{"question": "Which fruit makes up the largest portion?", "options": ["Apples", "Oranges", "Bananas"], "answer": "Apples"}},
                {{"question": "What percentage do Oranges represent?", "options": ["30%", "45%", "25%"], "answer": "30%"}}
            ]
        }})

        # Print the final JSON object to stdout
        print(json.dumps({{"plots": plot_metadata}}))

    if __name__ == "__main__":
        generate_all_plots()
    ```

    Now, generate a new, complete Python script that follows all these rules for the provided syllabus. Output ONLY the Python code inside a markdown block.
    """

    response_content = call_openrouter(api_key, model, prompt)
    python_code = _extract_code(response_content, 'python')

    with open(TEMP_PLOT_SCRIPT, 'w') as f:
        f.write(python_code)

    print(f"  > Executing generated script: {TEMP_PLOT_SCRIPT}")
    try:
        result = subprocess.run(
            ['python', TEMP_PLOT_SCRIPT],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        plots_json_str = result.stdout
        plots_json = json.loads(plots_json_str)
        print("✓ Plots generated and metadata captured successfully.")
        return plots_json
    except subprocess.CalledProcessError as e:
        print("--- ERROR: The generated Python script failed to execute. ---")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        raise
    except json.JSONDecodeError:
        print("--- ERROR: The generated script did not output valid JSON. ---")
        print("RAW OUTPUT:", result.stdout)
        raise
    finally:
        if os.path.exists(TEMP_PLOT_SCRIPT):
            os.remove(TEMP_PLOT_SCRIPT)


# --- 5. Step 3: Generate Worksheet Part 1 (Teaching) ---
def generate_worksheet_part1(api_key, syllabus_json):
    """
    Uses Gemini 2.5 Pro to generate the teaching section of the worksheet in LaTeX.
    """
    print("\n--- Step 3: Generating Worksheet Teaching Section ---")
    model = 'google/gemini-2.5-pro'
    prompt = f"""
    You are a LaTeX expert creating a science worksheet.
    Based on the provided syllabus, generate the teaching part of a worksheet.

    Syllabus: {json.dumps(syllabus_json, indent=2)}

    Create a LaTeX document that includes:
    1. A standard preamble: `documentclass{{article}}`, `usepackage{{graphicx}}`, `usepackage{{amsmath}}`, `usepackage{{geometry}}`.
    2. A title, an introduction, and a section for each sub-topic.

    Output ONLY the raw LaTeX code inside a markdown block.
    """

    response_content = call_openrouter(api_key, model, prompt)
    latex_part1 = _extract_code(response_content, 'latex')
    print("✓ Worksheet Part 1 (teaching section) generated.")
    return latex_part1


# --- 6. Step 4: Generate Worksheet Part 2 (Questions & Assembly) ---
def generate_worksheet_part2(api_key, latex_part1, plots_json):
    """
    Uses Gemini 2.5 Pro to add questions, plots, and an answer key to complete the LaTeX worksheet.
    """
    print("\n--- Step 4: Assembling Full Worksheet ---")
    model = 'google/gemini-2.5-pro'
    prompt = f"""
    You are a LaTeX expert finishing a science worksheet.
    You are given Part 1 of a LaTeX document and JSON data for plots.

    **LaTeX Part 1 (existing code):**
    ```latex
    {latex_part1}
    ```

    **Plot Data (for inclusion):**
    ```json
    {json.dumps(plots_json, indent=2)}
    ```

    **Your Task:**
    Append the following sections to the LaTeX document in this order:
    1.  **Data Interpretation Section**: For each plot, insert the image using its path, add its description, and list its MCQs.
    2.  **General Knowledge Section**: Generate 5 more MCQs, 3 True/False, 3 Fill-in-the-blank, and 3 Short Answer questions relevant to the overall topics.
    3.  **Answer Key**: Provide answers for ALL questions.
    4.  End the document with `\\end{{document}}`.

    Output ONLY the complete, final, raw LaTeX code inside a markdown block.
    """

    response_content = call_openrouter(api_key, model, prompt)
    full_latex = _extract_code(response_content, 'latex')
    print("✓ Full draft worksheet generated.")
    return full_latex


# --- 7. Step 5: Review and Refine Worksheet ---
def review_worksheet(api_key, full_latex, topics_list, plots_json):
    """
    Uses Gemini 2.5 Pro to review and refine the final LaTeX worksheet.
    """
    print("\n--- Step 5: Final Review ---")
    model = 'google/gemini-2.5-pro'
    prompt = f"""
    You are a meticulous editor and LaTeX expert reviewing a GED Science worksheet.

    **Original Topics:** {topics_list}
    **Plot Descriptions:** {[p.get('description', '') for p in plots_json.get('plots', [])]}
    **Draft LaTeX Code:**
    ```latex
    {full_latex}
    ```

    **Task:**
    Review the draft for completeness, correctness, question quality, and LaTeX syntax. Fix any issues you find directly in the code.
    Output a single, valid JSON object with the structure:
    `{{"issues_found": ["Description of fixes..."], "revised_latex": "The full, corrected LaTeX code."}}`

    If no issues, "issues_found" can be an empty list. Output only the JSON in a markdown block.
    """

    response_content = call_openrouter(api_key, model, prompt)
    review_json = _extract_json(response_content)

    issues = review_json.get('issues_found', [])
    if issues and issues[0]:  # Check if list has non-empty strings
        print("  > Reviewer found and fixed the following issues:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("  > Reviewer found no major issues.")

    final_latex = review_json['revised_latex']
    print("✓ Final review complete.")
    return final_latex


# --- 8. Main Orchestrator Function ---
def main():
    """
    Main function to orchestrate the entire worksheet generation workflow.
    """
    print("--- GED Science Worksheet Generator ---")
    try:
        api_key = load_api_key()

        topics_list, syllabus_json = get_and_generate_syllabus(api_key)
        plots_json = generate_plots(api_key, syllabus_json)
        latex_part1 = generate_worksheet_part1(api_key, syllabus_json)
        full_latex_draft = generate_worksheet_part2(api_key, latex_part1, plots_json)
        final_latex = review_worksheet(api_key, full_latex_draft, topics_list, plots_json)

        output_filename = 'final_worksheet.tex'
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(final_latex)

        print("\n--- Workflow Complete! ---")
        print(f"✓ Final worksheet saved to: {output_filename}")
        print(f"✓ Plot images saved in: {PLOTS_DIR}/")
        print(
            "\nTo view your worksheet, compile the .tex file using a LaTeX editor (like TeX Live, MiKTeX, or Overleaf).")

    except (ValueError, FileNotFoundError, requests.exceptions.RequestException, subprocess.CalledProcessError) as e:
        print(f"\n--- A critical error occurred ---")
        print(f"Error: {e}")
        print("Workflow aborted.")
    except Exception as e:
        print(f"\n--- An unexpected error occurred ---")
        print(f"Error: {e}")
        print("Workflow aborted.")


if __name__ == "__main__":
    main()