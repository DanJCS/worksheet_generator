import matplotlib.pyplot as plt
import numpy as np


def create_water_distribution_pie_chart():
    """
    Generates a pie chart showing the distribution of Earth's freshwater.
    This plot relates to "The Water Cycle" and highlights where freshwater,
    a critical resource, is located.

    Sample Questions:
    1. According to the chart, where is the largest portion of Earth's freshwater found?
    2. What percentage of Earth's freshwater is stored as groundwater?
    3. Based on this chart, why might access to fresh drinking water be a challenge,
       even though there is a lot of freshwater on Earth?
    """
    # Data for the distribution of Earth's freshwater
    sources = ['Glaciers & Ice Caps', 'Groundwater', 'Surface & Other Freshwater']
    percentages = [68.7, 30.1, 1.2]

    # Colors for each section
    colors = ['#ADD8E6', '#4682B4', '#5F9EA0']
    # Explode the smallest slice to make it more visible
    explode = (0, 0, 0.2)

    # --- Plotting ---
    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax.pie(
        percentages,
        explode=explode,
        labels=sources,
        colors=colors,
        autopct='%1.1f%%',  # Show percentages with one decimal place
        startangle=90,
        pctdistance=0.85,  # Distance of percentage text from center
        textprops={'fontsize': 10, 'fontweight': 'bold'}
    )

    # Draw a circle at the center to make it a donut chart
    centre_circle = plt.Circle((0, 0), 0.70, fc='white')
    fig.gca().add_artist(centre_circle)

    # --- Formatting ---
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    plt.title("Figure 5: Distribution of Earth's Freshwater", fontsize=14, fontweight='bold', pad=20)
    plt.setp(autotexts, size=10, weight="bold", color="white")

    # Show the plot
    plt.show()


def create_greenhouse_gas_pie_chart():
    """
    Generates a pie chart showing the sources of greenhouse gas emissions by economic sector.
    This plot relates to "Climate Change and Its Impacts," specifically the human
    activities that drive it.

    Sample Questions:
    1. Which economic sector is the largest source of greenhouse gas emissions shown in the chart?
    2. What is the combined percentage of emissions from the 'Electricity' and 'Industry' sectors?
    3. A student claims that agriculture is a bigger source of greenhouse gases than transportation.
       Does this chart support their claim?
    """
    # Data for sources of greenhouse gas emissions (approximate values)
    sectors = ['Transportation', 'Electricity', 'Industry', 'Agriculture', 'Commercial & Residential']
    percentages = [28, 25, 23, 11, 13]

    # Colors for each section
    colors = ['#FF6347', '#FFD700', '#8A2BE2', '#32CD32', '#1E90FF']
    # Explode the 'Transportation' slice to highlight the largest source
    explode = (0.05, 0, 0, 0, 0)

    # --- Plotting ---
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(
        percentages,
        explode=explode,
        labels=sectors,
        colors=colors,
        autopct='%1.0f%%',
        startangle=140,
        wedgeprops={'edgecolor': 'white', 'linewidth': 1}
    )

    # --- Formatting ---
    ax.axis('equal')
    plt.title("Figure 6: Sources of Greenhouse Gas Emissions by Sector", fontsize=14, fontweight='bold', pad=20)

    # Show the plot
    plt.show()


# --- Main execution block ---
if __name__ == "__main__":
    create_water_distribution_pie_chart()
    create_greenhouse_gas_pie_chart()