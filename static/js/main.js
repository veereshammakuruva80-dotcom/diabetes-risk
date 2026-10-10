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
});
