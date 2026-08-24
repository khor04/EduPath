// ================================
// Faculty -> Programme Mapping
// ================================
const programmes = {

    "Faculty of Built Environment": [
        "Bachelor of Science in Architecture",
        "Bachelor of Building Surveying",
        "Bachelor of Quantity Surveying",
        "Bachelor of Urban & Regional Planning",
        "Bachelor of Real Estate"
    ],

    "Faculty of Languages and Linguistics": [
        "Bachelor of English Language and Linguistics",
        "Bachelor of Chinese Language and Linguistics",
        "Bachelor of Arabic Language and Linguistics",
        "Bachelor of Tamil Language and Linguistics",
        "Bachelor of Japanese Language and Linguistics",
        "Bachelor of French Language and Linguistics",
        "Bachelor of German Language and Linguistics",
        "Bachelor of Spanish Language and Linguistics",
        "Bachelor of Italian Language and Linguistics"
    ],

    "Faculty of Pharmacy": [
        "Bachelor of Pharmacy"
    ],

    "Faculty of Nursing": [
        "Bachelor of Nursing Science"
    ],

    "Faculty of Engineering": [
        "Bachelor of Biomedical Engineering",
        "Bachelor of Chemical Engineering",
        "Bachelor of Civil Engineering",
        "Bachelor of Electrical Engineering",
        "Bachelor of Mechanical Engineering"
    ],

    "Faculty of Education": [
        "Bachelor of Counseling",
        "Bachelor of Education Teaching English as a Second Language",
        "Bachelor of Early Childhood Education"
    ],

    "Faculty of Dentistry": [
        "Bachelor of Dental Surgery"
    ],

    "Faculty of Business and Economics": [
        "Bachelor of Business Administration",
        "Bachelor of Accounting",
        "Bachelor of Finance",
        "Bachelor of Economics"
    ],

    "Faculty of Medicine": [
        "Bachelor of Biomedical Science",
        "Bachelor of Medicine and Bachelor of Surgery"
    ],

    "Faculty of Science": [
        "Bachelor of Science in Biotechnology",
        "Bachelor of Science in Biochemistry",
        "Bachelor of Science in Ecology and Biodiversity",
        "Bachelor of Science in Microbiology and Molecular Genetics",
        "Bachelor of Science in Mathematics",
        "Bachelor of Science in Statistics",
        "Bachelor of Actuarial Science",
        "Bachelor of Science in Chemistry",
        "Bachelor of Science in Physics",
        "Bachelor of Science with Education",
        "Bachelor of Science in Applied Geology",
        "Bachelor of Science in Environmental Management"
    ],

    "Faculty of Computer Science & Information Technology": [
        "Bachelor of Computer Science (Artificial Intelligence)",
        "Bachelor of Computer Science (Computer System and Network)",
        "Bachelor of Computer Science (Information Systems)",
        "Bachelor of Computer Science (Software Engineering)",
        "Bachelor of Computer Science (Multimedia Computing)",
        "Bachelor of Computer Science (Data Science)"
    ],

    "Faculty of Arts and Social Sciences": [
        "Bachelor of Arts Anthropology and Sociology",
        "Bachelor of Arts Chinese Studies",
        "Bachelor of Arts English",
        "Bachelor of Arts History",
        "Bachelor of Arts Indian Studies",
        "Bachelor of Arts International and Strategic Studies",
        "Bachelor of Arts Southeast Asian Studies",
        "Bachelor of East Asian Studies",
        "Bachelor of Environmental Studies",
        "Bachelor of Geography",
        "Bachelor of Media Studies",
        "Bachelor of Social Administration"
    ],

    "Faculty of Creative Arts": [
        "Bachelor of Dance",
        "Bachelor of Drama",
        "Bachelor of Music",
        "Bachelor of Performing Arts"
    ],

    "Faculty of Law": [
        "Bachelor of Law",
        "Bachelor of Jurisprudence"
    ],

    "Faculty of Sports and Exercise Science": [
        "Bachelor of Exercise Science",
        "Bachelor of Sports Management"
    ],

    "Academic of Islamic Studies": [
        "Bachelor of Islamic Studies and Science",
        "Bachelor of Muamalat Management",
        "Bachelor of Al-Quran and Al-Hadith",
        "Bachelor of Shariah and Law",
        "Bachelor of Shariah",
        "Bachelor of Usuluddin",
        "Bachelor of Islamic Education"
    ],

    "Academic of Malay Studies": [
        "Bachelor of Professional Malay Language",
        "Bachelor of Malay Linguistics",
        "Bachelor of Malay Literature",
        "Bachelor of Malay Studies"
    ]
};

function togglePassword(icon) {
    const input = icon.previousElementSibling;

    if (input.type === "password") {
        input.type = "text";
        icon.classList.replace("bi-eye-slash", "bi-eye");
    } else {
        input.type = "password";
        icon.classList.replace("bi-eye", "bi-eye-slash");
    }
}


// ================================
// Registration Setup
// ================================
document.addEventListener("DOMContentLoaded", function () {
const signupForm = document.getElementById("signupForm");
const confirmModal = new bootstrap.Modal(document.getElementById("confirmModal"));

const usernameInput = document.getElementById("username");
const emailInput = document.getElementById("email");

const usernameError = document.getElementById("usernameError");
const emailError = document.getElementById("emailError");

const passwordInput = document.getElementById("password");
const confirmPasswordInput = document.getElementById("confirmPassword");
const passwordRequirementMsg = document.getElementById("passwordRequirementMsg");
const passwordMatchMsg = document.getElementById("passwordMatchMsg");

const facultySelect = document.getElementById("faculty");
const programmeSelect = document.getElementById("programme");
const batchSelect = document.getElementById("batch");

let debounceTimer;

// availability state
let usernameValid = false;
let emailValid = false;
let requestCounter = 0;
let allowSubmit = false;

// ================================
// Real-time Username & Email Check
// ================================
async function forceAvailabilityCheck() {
    const res = await fetch("/check-availability", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            username: usernameInput.value.trim(),
            email: emailInput.value.trim()
        })
    });

    const data = await res.json();

    usernameValid = !data.username_taken;
    emailValid = !data.email_taken;

    usernameError.textContent = data.username_taken
        ? "Username already taken"
        : "";

    emailError.textContent = data.email_taken
        ? "Email already registered"
        : "";
}

async function checkAvailability() {
    clearTimeout(debounceTimer);

    debounceTimer = setTimeout(async () => {

        const currentRequest = ++requestCounter;

        const username = usernameInput.value.trim();
        const email = emailInput.value.trim();

        const res = await fetch("/check-availability", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, email })
        });

        const data = await res.json();

        // ❗ ignore old responses
        if (currentRequest !== requestCounter) return;

        usernameValid = !data.username_taken;
        emailValid = !data.email_taken;

        usernameError.textContent = data.username_taken
            ? "Username already taken"
            : "";

        emailError.textContent = data.email_taken
            ? "Email already registered"
            : "";

    }, 400);
}

facultySelect.addEventListener("change", function () {

    const selectedFaculty = this.value;

    programmeSelect.innerHTML =
        '<option value="">Select Programme</option>';

    if (programmes[selectedFaculty]) {

        programmes[selectedFaculty].forEach(programme => {

            const option = document.createElement("option");

            option.value = programme;
            option.textContent = programme;

            programmeSelect.appendChild(option);
        });
    }
});

// attach once
usernameInput.addEventListener("input", checkAvailability);
emailInput.addEventListener("input", checkAvailability);

// ================================
// Password Validation
// ================================

function validatePassword() {
    const password = passwordInput.value;

    const passwordRegex =
        /^(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{8,}$/;

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

// password match check
function checkPasswordMatch() {
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;

    if (confirmPassword.length === 0) {
        passwordMatchMsg.innerText = "";
        return;
    }

    if (password === confirmPassword) {
        passwordMatchMsg.innerText = "Password matched";
        passwordMatchMsg.style.color = "green";
    } else {
        passwordMatchMsg.innerText = "Password does not match";
        passwordMatchMsg.style.color = "red";
    }
}

passwordInput.addEventListener("input", () => {
    validatePassword();
    checkPasswordMatch();
});

confirmPasswordInput.addEventListener("input", checkPasswordMatch);

// ================================
// Form Submit Handler
// ================================

signupForm.addEventListener("submit", async function (e) {

    if (allowSubmit) return;

    e.preventDefault();

    // password validation
    const passwordValid = validatePassword();
    if (!passwordValid) return;

    if (passwordInput.value !== confirmPasswordInput.value) {
        passwordMatchMsg.innerText = "Password does not match";
        passwordMatchMsg.style.color = "red";
        return;
    }

    await forceAvailabilityCheck();

    // availability check gate
    if (!usernameValid || !emailValid) {
        usernameError.textContent ||= "Please fix errors before continuing";
        emailError.textContent ||= "Please fix errors before continuing";
        return;
    }

    // show confirmation modal data
    const facultyText = facultySelect?.selectedOptions?.[0]?.text || "";
    const programmeText = programmeSelect?.selectedOptions?.[0]?.text || "";
    const batchText = batchSelect?.selectedOptions?.[0]?.text || "";

    document.getElementById("confirmFaculty").textContent = facultyText;
    document.getElementById("confirmProgramme").textContent = programmeText;
    document.getElementById("confirmBatch").textContent = batchText;

    confirmModal.show();
});

// ================================
// Confirm Button Submit
// ================================

document.getElementById("confirmRegisterBtn")
    .addEventListener("click", function () {
        allowSubmit = true;
        signupForm.submit();
    });

});