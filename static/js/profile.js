let isEditing = false;

function enableEdit(event) {
    event.preventDefault();

    const usernameInput = document.getElementById("usernameInput");
    const emailInput = document.getElementById("emailInput")
    const editBtn = document.getElementById("editSaveBtn");
    const profileForm = document.getElementById("profileForm");

    if (!isEditing) {
        //enable editing
        usernameInput.readOnly = false;
        emailInput.readOnly = false;

        usernameInput.focus();

        editBtn.innerText = "Save";
        isEditing = true;
    } else {
        usernameInput.readOnly = false;
        emailInput.readOnly = false;
        profileForm.submit();

        //reset ui state
        editBtn.innerText = "Edit";
        isEditing = false;
    }
}

function openModal(id) {
    document.getElementById(id).style.display = "flex";
}

function closeModal(id) {
    document.getElementById(id).style.display = "none";
}

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

document.addEventListener("DOMContentLoaded", function () {

    const currentPassword = document.getElementById("currentPassword");
    const newPassword = document.getElementById("newPassword");
    const confirmPassword = document.getElementById("confirmPassword");

    const currentPasswordMsg = document.getElementById("currentPasswordMsg");
    const passwordRequirementMsg = document.getElementById("passwordRequirementMsg");
    const passwordMatchMsg = document.getElementById("passwordMatchMsg");

    const passwordSaveBtn = document.getElementById("passwordSaveBtn");

    let currentPasswordValid = false;
    let passwordMatchValid = false;
    let passwordComplexityValid = false;

    async function checkCurrentPassword() {

        if (!currentPassword.value) {
            currentPasswordMsg.innerText = "";
            currentPasswordValid = false;
            updateSaveButton();
            return;
        }

        try {
            const response = await fetch("/check-current-password", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    current_password: currentPassword.value
                })
            });

            const data = await response.json();

            if (!data.valid) {
                currentPasswordMsg.innerText = "Current password is incorrect.";
                currentPasswordMsg.style.color = "red";
                currentPasswordValid = false;
            } else {
                currentPasswordMsg.innerText = "";
                currentPasswordValid = true;
            }

            updateSaveButton();

        } catch (error) {
            console.error("Error checking current password:", error);
            currentPasswordValid = false;
            updateSaveButton();
        }
    }

    function validatePassword() {

        const password = newPassword.value;

        // Minimum 8 characters, 1 digit, 1 special character
        const regex =
            /^(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{8,}$/;

        if (password.length === 0) {
            passwordRequirementMsg.innerText = "";
            passwordComplexityValid = false;
            updateSaveButton();
            return;
        }

        if (regex.test(password)) {
            passwordRequirementMsg.innerText =
                "✓ Password meets requirements";
            passwordRequirementMsg.style.color = "green";
            passwordComplexityValid = true;
        } else {
            passwordRequirementMsg.innerText =
                "Password must be at least 8 characters and contain 1 digit and 1 special character";
            passwordRequirementMsg.style.color = "red";
            passwordComplexityValid = false;
        }

        updateSaveButton();
    }

    function checkPasswordMatch() {

        if (!newPassword.value || !confirmPassword.value) {
            passwordMatchMsg.innerText = "";
            passwordMatchValid = false;
            updateSaveButton();
            return;
        }

        if (newPassword.value === confirmPassword.value) {
            passwordMatchMsg.innerText = "✓ Password matched";
            passwordMatchMsg.style.color = "green";
            passwordMatchValid = true;
        } else {
            passwordMatchMsg.innerText =
                "New password and confirm password do not match.";
            passwordMatchMsg.style.color = "red";
            passwordMatchValid = false;
        }

        updateSaveButton();
    }

    function updateSaveButton() {
        passwordSaveBtn.disabled = !(
            currentPasswordValid &&
            passwordMatchValid &&
            passwordComplexityValid
        );
    }

    currentPassword.addEventListener("input", checkCurrentPassword);

    newPassword.addEventListener("input", function () {
        validatePassword();
        checkPasswordMatch();
    });

    confirmPassword.addEventListener("input", checkPasswordMatch);

    updateSaveButton();
});

function previewProfilePicture(event) {
    const file = event.target.files[0];
    const preview = document.getElementById("profilePicturePreview");

    if (file) {
        preview.src = URL.createObjectURL(file);
    }
}