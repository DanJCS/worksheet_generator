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
    """Retrieves the OpenRouter API key from environment variables."""
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise ValueError("Error: OPENROUTER_API_KEY environment variable not set.")
    print("✓ API Key loaded successfully.")
    return api_key


# --- 2. Helper Function: Call OpenRouter API ---
def call_openrouter(api_key, model, prompt):
    """Sends a request to the OpenRouter API and returns the model's raw response."""
    print(f"  > Calling model: {model}...")
    try:
        response = requests.post(
            url=OPENROUTER_API_URL,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            data=json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]}),
            timeout=300  # Increased timeout for very large worksheet generation
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
    pattern = re.compile(rf'```{language}\n(.*?)\n```', re.DOTALL)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    if text.strip().startswith('```') and text.strip().endswith('```'):
        return text.strip()[3:-3].strip()
    return text


def _extract_json(text):
    """Extracts a JSON object from a markdown block or raw text."""
    json_str = _extract_code(text, 'json')
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"Could not parse JSON from response: {e}")
            raise


# --- Step 1: Get User Input and Generate Syllabus ---
def get_and_generate_syllabus(api_key):
    """Prompts user for topics and uses Gemini 2.5 Pro to generate a syllabus."""
    print("\n--- Step 1: Defining Syllabus ---")
    topics_list = input("Enter 1-2 GED Science topics (e.g., 'Genetics and DNA, Chemical Reactions'): ")
    if not topics_list:
        raise ValueError("Topic list cannot be empty.")

    model = 'perplexity/sonar'
    prompt = f"""
    You are an expert curriculum developer for the GED Science test.
    Research the following user-provided topics: "{topics_list}".
    Break these topics down into a single main chapter, a specific lesson title, and up to 6 teachable sub-topics with concise descriptions.

    Output your response as a single, valid JSON object inside a JSON markdown block.
    Example Structure:
    ```json
    {{
      "chapter_name": "Life Science",
      "lesson_title": "The Structure of DNA",
      "sub_topics": [
        {{ "name": "Nucleotides", "description": "The building blocks of DNA..." }},
        {{ "name": "The Double Helix", "description": "The twisted ladder structure..." }}
      ]
    }}
    ```
    """
    response_content = call_openrouter(api_key, model, prompt)
    syllabus_json = _extract_json(response_content)
    print(f"✓ Syllabus generated for '{topics_list}'.")
    return topics_list, syllabus_json


# --- Step 2: Generate Plots via Executable Python Code ---
def generate_plots(api_key, syllabus_json):
    """Uses Gemini to write Python code that generates plots, then executes that code."""
    print("\n--- Step 2: Generating Data Visualizations ---")
    model = 'google/gemini-2.5-pro'
    # --- PROMPT CHANGE IS HERE ---
    prompt = f"""
    You are an expert Python programmer specializing in `matplotlib`. Your task is to write a complete, self-contained Python script that generates 1 or 2 data plots relevant to the following science syllabus and then prints a JSON object with their metadata.

    **Syllabus for Context:**
    {json.dumps(syllabus_json, indent=2)}

    **Requirements for the Python Script you will write:**
    1.  It must import `os`, `matplotlib.pyplot`, `json`, and `time`.
    2.  It must create a directory named `./plots` if it doesn't exist.
    3.  It must generate one or two relevant plot types from: `bar`, `line`, `scatter`, `pie`.
    4.  For each plot:
        - Generate realistic sample data.
        - Set a clear title and labels.
        - **For pie charts, ensure slice labels are legible by using `textprops={{'color':"black", 'size':'large'}}`.**
        - Save the plot as a PNG file to the `./plots` directory with a unique name.
    5.  After saving the plots, it must create a list of dictionaries, one for each plot, containing: `path`, a `description`, and two `mcqs`.
    6.  Finally, the script MUST print a single JSON object containing a key "plots" which holds the list of plot metadata. This is the only thing it should print.

    **Example of the Python script's final print statement:**
    `print(json.dumps({{"plots": plot_metadata_list}}))`

    Now, generate a new, complete Python script that follows all these rules for the provided syllabus. Output ONLY the Python code inside a markdown block.
    """
    response_content = call_openrouter(api_key, model, prompt)
    python_code = _extract_code(response_content, 'python')

    with open(TEMP_PLOT_SCRIPT, 'w', encoding='utf-8') as f:
        f.write(python_code)

    print(f"  > Executing generated script: {TEMP_PLOT_SCRIPT}")
    try:
        result = subprocess.run(
            ['python', TEMP_PLOT_SCRIPT], capture_output=True, text=True, check=True, encoding='utf-8'
        )
        plots_json_str = result.stdout
        plots_json = json.loads(plots_json_str)
        print("✓ Plots generated and metadata captured successfully.")
        return plots_json
    except subprocess.CalledProcessError as e:
        print("--- ERROR: The generated Python script failed to execute. ---")
        print("STDERR:", e.stderr)
        raise
    except json.JSONDecodeError:
        print("--- WARNING: The generated script did not output valid JSON or no plots were created. ---")
        print("RAW OUTPUT:", result.stdout)
        # Return the expected dictionary structure, but empty.
        return {"plots": []}
    finally:
        if os.path.exists(TEMP_PLOT_SCRIPT):
            os.remove(TEMP_PLOT_SCRIPT)


# --- Step 3: Generate Full Worksheet from Template ---
def generate_full_worksheet(api_key, syllabus_json, plots_json):
    """
    Uses Gemini 2.5 Pro to generate a complete worksheet based on a detailed template.
    This function replaces the old part1/part2 generation steps.
    """
    print("\n--- Step 3: Generating Full Worksheet from Template ---")
    model = 'google/gemini-2.5-pro'

    # --- ROBUSTNESS FIX IS HERE ---
    # Check if plots_json is a dict with a 'plots' key, or just a list of plots.
    plot_list = []
    if isinstance(plots_json, dict):
        plot_list = plots_json.get("plots", [])
    elif isinstance(plots_json, list):
        plot_list = plots_json

    # Construct the plot section for the prompt, if plots exist
    plot_section_prompt = ""
    if plot_list:
        plot_section_prompt = f"""
#### **Section C: Data Interpretation**

***Analyze the following data visualization(s) and answer the related questions.***
"""
        for plot in plot_list:
            # Ensure we handle cases where plot might not be a dict (highly unlikely but safe)
            if isinstance(plot, dict):
                plot_section_prompt += f"""
[Insert plot image here with path: {plot.get('path', '')}]
[Insert the plot's description here: "{plot.get('description', '')}"]
[Insert the two MCQs for this plot here: {json.dumps(plot.get('mcqs', []))}]
"""

    prompt = f"""
    You are an expert curriculum designer and LaTeX specialist. Your task is to create a complete GED Science Daily Worksheet based on the provided syllabus and a strict template.

    **INPUT SYLLABUS:**
    ```json
    {json.dumps(syllabus_json, indent=2)}
    ```

    **YOUR TASK:**
    Generate a complete LaTeX document by perfectly following the structure and instructions in the template below. You must populate all sections with original, relevant content based on the input syllabus.

    --- TEMPLATE START ---

    \\documentclass{{article}}
    \\usepackage{{amsmath}}
    \\usepackage{{graphicx}}
    \\usepackage[margin=1in]{{geometry}}
    \\usepackage{{amsfonts}}
    \\usepackage{{amssymb}}
    \\usepackage{{array}}
    \\newcolumntype{{L}}{{>{{\\raggedright\\arraybackslash}}p{{0.4\\textwidth}}}}
    \\newcolumntype{{R}}{{>{{\\raggedright\\arraybackslash}}p{{0.4\\textwidth}}}}

    \\begin{{document}}

    \\section*{{GED Science Daily Worksheet: {syllabus_json.get('chapter_name', 'Science')}}}

    **Topic of the Day:** {syllabus_json.get('lesson_title', 'Core Concepts')} \\\\
    **GED Science Practices Focus:** Comprehend Scientific Presentations, Reason with Scientific Information, Express and Apply Scientific Information

    \\hrulefill

    \\subsection*{{Part 1: Core Concepts (Learn)}}

    % Designer's Guide: Use the sub_topics from the syllabus to create a clear, concise mini-lesson.
    % Use \\subsubsection* for each sub-topic name.
    % Use \\textbf{{}} for all critical vocabulary words.
    % Structure the content logically (e.g., step-by-step, compare/contrast).
    % This should be an intuitive guide, rather than a detailed and wordy series of explanations. 
    % Use tcolorbox for nice formatting to keep the sub-topics well-separated.

    [Generate the Core Concepts section here based on the 'sub_topics' in the syllabus. Each sub-topic should be a subsection with its description elaborated into a clear paragraph.]

    \\hrulefill

    \\subsection*{{Part 2: GED-Style Practice (Test)}}
    % Keep the problems appropriately spaced out
    
    \\subsubsection*{{Section A: Direct Application Questions}}

    % Generate 5 standard multiple-choice questions.
    % Generate 1 "drop-down" style question.
    % Generate 1 "matching" style question.

    \\subsubsection*{{Section B: Passage-Based Questions}}

    % Generate two separate scientific passages (<150 words each) related to the lesson.
    % Generate two multiple-choice questions for each passage.

    {plot_section_prompt} % This will be empty if no plots were generated

    \\hrulefill

    \\subsection*{{Part 3: Revision + Active Recall}}

    \\subsubsection*{{Section A: True or False?}}

    % Generate 6 True/False statements.

    \\subsubsection*{{Section B: Fill in the Blanks}}

    % Provide a Word Bank and a summary paragraph with 3-5 blanks.

    \\subsubsection*{{Section C: Short Answer Challenge}}

    % Write one open-ended question requiring a 2-4 sentence response using specific vocabulary.

    \\hrulefill

    \\subsection*{{Answer Key & Explanations}}

    % Provide a detailed answer key for ALL questions from Part 2 and Part 3.
    % For MCQs, include the correct letter and a brief explanation.
    % For T/F, list the correct answers.
    % For Fill-in-the-blanks, list the correct words.
    % For the Short Answer, provide a model response.
    % Place the Answer Key and Explanation in a new page

    \\end{{document}}

    --- TEMPLATE END ---

    **FINAL INSTRUCTIONS:**
    1.  Fill in every section of the template.
    2.  For the plot section, use `\\includegraphics[width=0.7\\textwidth]{{{plot['path']}}}` to include the images.
    3.  Ensure all generated content is accurate and relevant to the provided syllabus.
    4.  Output ONLY the complete, raw LaTeX code. Do not include any other text, explanations, or markdown formatting.
    """

    response_content = call_openrouter(api_key, model, prompt)
    full_latex = _extract_code(response_content, 'latex')
    print("✓ Full worksheet generated from template.")
    return full_latex


# --- Step 4: Review and Refine Worksheet ---
def review_worksheet(api_key, full_latex, syllabus_json, plots_json):
    """
    Uses Kimi K2 Instruct to review and refine the final LaTeX worksheet.
    This function is fault-tolerant: if the review fails, it returns the un-reviewed draft.
    """
    print("\n--- Step 4: Final Review ---")
    model = 'google/gemini-2.5-flash'

    prompt = f"""
    You are a meticulous editor and LaTeX expert reviewing a GED Science worksheet. Your primary goal is to ensure the generated content strictly adheres to the provided syllabus.

    **Authoritative Syllabus (This is the ground truth):**
    ```json
    {json.dumps(syllabus_json, indent=2)}
    ```

    **Plot Descriptions (for context):**
    {[p.get('description', '') for p in plots_json.get('plots', [])]}

    **Draft LaTeX Code to Review:**
    ```latex
    {full_latex}
    ```
    **Task:**
    Review the draft against the authoritative syllabus. Check for completeness, factual correctness, question quality, and LaTeX syntax. Fix any errors or deviations from the syllabus directly in the code.

    Output a single, valid JSON object with the structure:
    `{{"issues_found": ["Description of fixes..."], "revised_latex": "The full, corrected LaTeX code."}}`

    If no issues, "issues_found" can be an empty list. Output only the JSON in a markdown block.
    """

    try:
        response_content = call_openrouter(api_key, model, prompt)
        review_json = _extract_json(response_content)

        issues = review_json.get('issues_found', [])
        if issues and issues[0]:
            print("  > Reviewer found and fixed the following issues:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  > Reviewer found no major issues.")

        final_latex = review_json.get('revised_latex')
        if not final_latex:
            # Handle cases where the 'revised_latex' key is missing from the JSON
            raise KeyError("Reviewer JSON response did not contain 'revised_latex' key.")

        print("✓ Final review complete.")
        return final_latex

    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        # --- THIS IS THE CRITICAL FALLBACK ---
        print("\n--- WARNING: The review step failed to produce a valid response. ---")
        print(f"Error details: {e}")
        print("The un-reviewed draft will be used instead. Please check the final .tex file carefully.")
        # Return the original, un-reviewed LaTeX so the program can finish.
        return full_latex

# --- 5. Main Orchestrator Function ---
def main():
    """Main function to orchestrate the entire worksheet generation workflow."""
    print("--- GED Science Worksheet Generator ---")
    try:
        api_key = load_api_key()

        # Step 1: Get topics and generate a structured syllabus
        # We no longer need topics_list after this step, as syllabus_json is more detailed.
        _, syllabus_json = get_and_generate_syllabus(api_key)

        # Step 2: Generate plots (if applicable)
        plots_json = generate_plots(api_key, syllabus_json)

        # Step 3: Generate the entire worksheet in one go using the new template
        full_latex_draft = generate_full_worksheet(api_key, syllabus_json, plots_json)

        # CHANGE 2: Pass the detailed syllabus_json to the reviewer, not the old topics_list.
        final_latex = review_worksheet(api_key, full_latex_draft, syllabus_json, plots_json)

        output_filename = 'final_worksheet.tex'
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(final_latex)

        print("\n--- Workflow Complete! ---")
        print(f"✓ Final worksheet saved to: {output_filename}")
        print(f"✓ Plot images saved in: {PLOTS_DIR}/")
        print("\nTo view your worksheet, compile the .tex file using a LaTeX editor (like TeX Live, MiKTeX, or Overleaf).")

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