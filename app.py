from flask import Flask, render_template, request, send_file, redirect, url_for, session
import datetime
from fpdf import FPDF
import io

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Needed for session management

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            # Trip Information
            departure_date_str = request.form.get("departure_date")
            return_date_str = request.form.get("return_date")

            departure_date = datetime.datetime.strptime(departure_date_str, "%Y-%m-%d").date()
            return_date = datetime.datetime.strptime(return_date_str, "%Y-%m-%d").date()

            trip_duration_days = (return_date - departure_date).days + 1  # Include departure and return day

            # Medication-specific fields
            medication_names = request.form.getlist("medication_name")
            dosage_quantities = request.form.getlist("dosage_quantity")
            dosage_intervals = request.form.getlist("dosage_interval")
            dosage_intervals_other = request.form.getlist("dosage_interval_other")
            current_counts = request.form.getlist("current_count")
            last_refill_dates = request.form.getlist("last_refill_date")
            doses_at_refills = request.form.getlist("doses_at_refill")
            extra_doses_list = request.form.getlist("extra_doses")

            # Sanity check: All fields must be the same length
            entries_count = len(medication_names)
            if not all(len(lst) == entries_count for lst in [
                dosage_quantities, dosage_intervals, dosage_intervals_other,
                current_counts, last_refill_dates, doses_at_refills, extra_doses_list
            ]):
                raise ValueError("Form submission fields are inconsistent in length.")

            today = datetime.date.today()

            medication_results = []
            action_summary = []
            timeline = []

            for i in range(entries_count):
                try:
                    medication_name = medication_names[i].strip() or "Unnamed Medication"
                    dosage_quantity = float(dosage_quantities[i] or 0)

                    interval_value = dosage_intervals[i]
                    interval_other = dosage_intervals_other[i]

                    if interval_value == "other" and interval_other:
                        days_between_doses = int(interval_other)
                    else:
                        days_between_doses = float(interval_value)

                    current_count = int(current_counts[i] or 0)
                    last_refill_date = datetime.datetime.strptime(last_refill_dates[i], "%Y-%m-%d").date()
                    doses_at_refill = int(doses_at_refills[i] or 0)
                    extra_doses = int(extra_doses_list[i] or 0)

                    if days_between_doses <= 0:
                        raise ValueError(f"Invalid entry: Days between doses must be > 0 for {medication_name}.")

                    effective_doses_per_day = 1 / days_between_doses
                    total_doses_per_day = dosage_quantity * effective_doses_per_day

                    pills_needed_for_trip = total_doses_per_day * trip_duration_days
                    total_needed = int(pills_needed_for_trip + extra_doses + 0.999)  # Always round up

                    normal_refill_available = doses_at_refill
                    available_total = current_count + normal_refill_available

                    must_refill_by = departure_date - datetime.timedelta(days=1)

                    # Determine Status
                    if current_count >= total_needed:
                        status = "✅ You have enough doses on hand."
                        must_refill = None
                        extra_refill_amount = None
                    elif available_total >= total_needed:
                        status = "🟡 You will need a refill, but your regular refill will cover the required doses."
                        must_refill = must_refill_by
                        extra_refill_amount = None
                        action_summary.append(f"Refill {medication_name} by {must_refill.strftime('%B %d, %Y')}.")
                        timeline.append({
                            "date": must_refill.strftime('%B %d, %Y'),
                            "action": f"Refill {medication_name} (normal refill)"
                        })
                    else:
                        status = "🔴 You will need more than your usual refill amount to have enough doses."
                        must_refill = must_refill_by
                        extra_refill_amount = int(total_needed - available_total + 0.999)  # Round up
                        action_summary.append(f"Request {extra_refill_amount} extra doses of {medication_name} by {must_refill.strftime('%B %d, %Y')}.")
                        timeline.append({
                            "date": must_refill.strftime('%B %d, %Y'),
                            "action": f"Request extra {extra_refill_amount} doses for {medication_name}"
                        })

                    medication_results.append({
                        "Medication": medication_name,
                        "Total Needed": str(total_needed),
                        "Status": status,
                        "Must Refill By": must_refill.strftime('%B %d, %Y') if must_refill else None,
                        "Extra Refill Amount": extra_refill_amount
                    })

                except Exception as e:
                    medication_results.append({
                        "Medication": f"Error in entry {i+1}",
                        "Status": f"Error: {str(e)}",
                        "Must Refill By": None,
                        "Extra Refill Amount": None
                    })

            # Save to session
            session["medication_results"] = medication_results
            session["action_summary"] = action_summary
            session["timeline"] = timeline
            session["departure_date"] = departure_date.strftime('%B %d, %Y')

            return redirect(url_for('results'))

        except Exception as e:
            return f"An error occurred while processing the form: {str(e)}", 400

    return render_template("form.html")

@app.route("/results")
def results():
    medication_results = session.get("medication_results", [])
    action_summary = session.get("action_summary", [])
    timeline = session.get("timeline", [])
    departure_date = session.get("departure_date", "Unknown")

    return render_template("results.html",
        medication_results=medication_results,
        action_summary=action_summary,
        timeline=timeline,
        departure_date=departure_date
    )

@app.route("/generate_pdf")
def generate_pdf():
    medication_results = session.get("medication_results", [])
    departure_date = session.get("departure_date", "Unknown")

    # Create a copy of medication_results with emoji replaced
    pdf_results = []
    for entry in medication_results:
        pdf_entry = entry.copy()
        if "Status" in pdf_entry:
            # Replace emoji with text equivalents
            status = pdf_entry["Status"]
            status = status.replace("✅", "[OK]")
            status = status.replace("🟡", "[WARNING]")
            status = status.replace("🔴", "[ALERT]")
            pdf_entry["Status"] = status
        pdf_results.append(pdf_entry)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, "Travel Medication Checklist", ln=True, align="C")
    pdf.ln(10)

    pdf.cell(0, 10, f"Departure Date: {departure_date}", ln=True)
    pdf.ln(5)

    for entry in pdf_results:
        for k, v in entry.items():
            if v is not None:  # Only print non-None values
                pdf.cell(0, 10, f"{k}: {v}", ln=True)
        pdf.ln(5)

    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    pdf_output = io.BytesIO(pdf_bytes)
    pdf_output.seek(0)

    return send_file(pdf_output, download_name="travel_medications.pdf", as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
