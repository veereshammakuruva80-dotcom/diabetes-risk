/**
 * AI-Based Diabetes Risk Prediction System - Frontend JavaScript
 * Member 1: Authentication, Form Validation & UI Interactions
 */

document.addEventListener("DOMContentLoaded", () => {
    // 1. Alert Dismissal
    const closeButtons = document.querySelectorAll(".alert-close");
    closeButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const alert = btn.closest(".alert");
            if (alert) {
                alert.style.opacity = "0";
                alert.style.transform = "translateY(-8px)";
                setTimeout(() => alert.remove(), 250);
            }
        });
    });

    // Auto-dismiss alerts after 6 seconds
    const alerts = document.querySelectorAll(".alert");
    alerts.forEach(alert => {
        setTimeout(() => {
            if (document.body.contains(alert)) {
                alert.style.opacity = "0";
                alert.style.transform = "translateY(-8px)";
                setTimeout(() => alert.remove(), 250);
            }
        }, 6000);
    });

    // 2. Password Visibility Toggle
    const toggleBtns = document.querySelectorAll(".password-toggle-btn");
    toggleBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-target");
            const input = document.getElementById(targetId);
            if (input) {
                if (input.type === "password") {
                    input.type = "text";
                    btn.textContent = "Hide";
                } else {
                    input.type = "password";
                    btn.textContent = "Show";
                }
            }
        });
    });

    // 3. Client-side Form Validation Helpers
    const registerForm = document.getElementById("register-form");
    if (registerForm) {
        registerForm.addEventListener("submit", (e) => {
            const pass = document.getElementById("password").value;
            const confirmPass = document.getElementById("confirm_password").value;

            if (pass !== confirmPass) {
                e.preventDefault();
                alert("Passwords do not match. Please re-enter.");
                return false;
            }
            if (pass.length < 8) {
                e.preventDefault();
                alert("Password must be at least 8 characters long.");
                return false;
            }
        });
    }

    // 4. Member 2: Health Data Form Client Validation & Duplicate Prevention
    const healthDataForm = document.getElementById("health-data-form");
    if (healthDataForm) {
        healthDataForm.addEventListener("submit", (e) => {
            const glucose = parseFloat(document.getElementById("glucose")?.value);
            const bp = parseFloat(document.getElementById("blood_pressure")?.value);
            const bmi = parseFloat(document.getElementById("bmi")?.value);
            const pedigree = parseFloat(document.getElementById("diabetes_pedigree_function")?.value);
            const age = parseInt(document.getElementById("age")?.value);

            let hasError = false;
            let errorMsg = "";

            if (isNaN(glucose) || glucose < 40 || glucose > 500) {
                hasError = true;
                errorMsg = "Glucose must be a valid number between 40 and 500 mg/dL.";
            } else if (isNaN(bp) || bp < 40 || bp > 250) {
                hasError = true;
                errorMsg = "Blood Pressure must be a valid number between 40 and 250 mm Hg.";
            } else if (isNaN(bmi) || bmi < 10 || bmi > 70) {
                hasError = true;
                errorMsg = "BMI must be a valid number between 10.0 and 70.0.";
            } else if (isNaN(pedigree) || pedigree < 0.05 || pedigree > 3.0) {
                hasError = true;
                errorMsg = "Diabetes Pedigree Function must be between 0.05 and 3.00.";
            } else if (isNaN(age) || age < 1 || age > 120) {
                hasError = true;
                errorMsg = "Age must be an integer between 1 and 120.";
            }

            if (hasError) {
                e.preventDefault();
                alert(errorMsg);
                return false;
            }

            // Prevent accidental duplicate submissions
            const submitBtn = document.getElementById("btn-submit-health-data");
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerText = "Recording Data...";
            }
        });
    }
});
