from flask import Flask, render_template, request, send_file
import datetime
from fpdf import FPDF
import io

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Extract lists
        medication_names = request.form.getlist("medication_name")
        dosage_frequencies = request.form.getlist("dosage_frequency")
        days_between_doses_list = request.form.getlist("days_between_doses")
        duration_days_list = request.form.getlist("duration_days")
        current_counts = request.form.getlist("current_count")
        last_refill_dates = request.form.getlist("last_refill_date")
        days_supply_from_refills = request.form.getlist("days_supply_from_refill")
        buffer_percentage = float(request.form.get("buffer_percentage", 5.0))

        today = datetime.date.today()

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, "Travel Medication Checklist", ln=True, align="C")
        pdf.ln(10)

        for i in range(len(medication_names)):
            try:
                dosage_frequency = float(dosage_frequencies[i])
                days_between_doses = int(days_between_doses_list[i])
                duration_days = int(duration_days_list[i])
                current_count = int(current_counts[i])
                last_refill_date = datetime.datetime.strptime(last_refill_dates[i], "%Y-%m-%d").date()
                days_supply_from_refill = int(days_supply_from_refills[i])

                effective_doses_per_day = dosage_frequency / days_between_doses
                pills_needed_for_trip = effective_doses_per_day * duration_days
                buffer_pills = pills_needed_for_trip * (buffer_percentage / 100)
                total_needed = pills_needed_for_trip + buffer_pills
                days_left_current_supply = current_count / effective_doses_per_day
                runout_date = today + datetime.timedelta(days=int(days_left_current_supply))
                expected_runout_from_refill = last_refill_date + datetime.timedelta(days=days_supply_from_refill)

                fields = {
                    "Medication": medication_names[i],
                    "Pills Needed": f"{pills_needed_for_trip:.1f}",
                    "Extra Buffer": f"{buffer_pills:.1f}",
                    "Total Needed": f"{total_needed:.1f}",
                    "Current Supply": f"{current_count}",
                    "Runout Date (Current Count)": f"{runout_date}",
                    "Runout Date (Refill)": f"{expected_runout_from_refill}"
                }

                for k, v in fields.items():
                    pdf.cell(0, 10, f"{k}: {v}", ln=True)
                pdf.ln(5)

            except Exception as e:
                pdf.cell(0, 10, f"Error processing entry {i+1}: {str(e)}", ln=True)
                pdf.ln(5)

        pdf_output = io.BytesIO()
        pdf.output(pdf_output)
        pdf_output.seek(0)

        return send_file(pdf_output, download_name="travel_medications.pdf", as_attachment=True)

    return render_template("form.html")

if __name__ == "__main__":
    app.run(debug=True)
