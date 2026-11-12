
const healthBtn = document.getElementById("healthBtn");
const healthResult = document.getElementById("healthResult");

healthBtn.addEventListener("click", async () => {
    healthResult.textContent = "Checking application...";
    
    try {
        const response = await fetch("/health");
        const data = await response.json();

        if (!response.ok) {
            throw new Error("Health check failed");
        }

        healthResult.textContent = "Application Status: " + data.status;
    } catch (error) {
        healthResult.textContent = "Unable to connect to application.";
    }
});

const greetBtn = document.getElementById("greetBtn");
const nameInput = document.getElementById("nameInput");
const greetResult = document.getElementById("greetResult");

greetBtn.addEventListener("click", async () => {
    const name = nameInput.value.trim();

    if (!name) {
        greetResult.textContent = "Please enter your name.";
        return;
    }

    greetResult.textContent = "Sending request...";

    try {
        const response = await fetch(
            "/api/greet?name=" + encodeURIComponent(name)
        );

        const data = await response.json();

        if (!response.ok) {
            greetResult.textContent = "Error: " + data.error;
            return;
        }

        greetResult.textContent = data.message;
    } catch (error) {
        greetResult.textContent = "Unable to connect to application.";
    }
});
