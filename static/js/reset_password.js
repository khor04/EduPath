function togglePassword(inputId, icon) {

    const input = document.getElementById(inputId);

    if (input.type === "password") {
        input.type = "text";

        icon.classList.remove("bi-eye-slash");
        icon.classList.add("bi-eye");

    } else {
        input.type = "password";

        icon.classList.remove("bi-eye");
        icon.classList.add("bi-eye-slash");
    }
}

// ================================
// Real-time Password Validation
// ================================

const resetPasswordInput = document.getElementById("resetPassword");
const passwordRequirementMsg = document.getElementById("passwordRequirementMsg");
const resetSubmitBtn = document.getElementById("resetSubmitBtn");

const passwordRegex =
    /^(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{8,}$/;

function validatePassword() {
    const password = resetPasswordInput.value;

    if (password.length === 0) {
        passwordRequirementMsg.innerText = "";
        return false;
    }

    if (passwordRegex.test(password)) {
        passwordRequirementMsg.innerText = "✓ Password meets requirements";
        passwordRequirementMsg.style.color = "green";
        return true;
    } else {
        passwordRequirementMsg.innerText =
            "Password must be at least 8 characters and contain 1 digit and 1 special character";
        passwordRequirementMsg.style.color = "red";
        return false;
    }
}

resetPasswordInput.addEventListener("input", () => {
    resetSubmitBtn.disabled = !validatePassword();
});
