
async function main() {
    try {
        const { GoogleGenAI } = await import("@google/genai");

        const apiKey =
            process.env.GEMINI_API_KEY ||
            process.env.GOOGLE_API_KEY;

        if (!apiKey) {
            throw new Error("Gemini API key not configured.");
        }

        const ai = new GoogleGenAI({ apiKey });

        console.log("Connecting to Gemini...");

        const response = await ai.models.generateContent({
            model: "gemini-flash-latest",
            contents: "Hello Gemini! Introduce yourself to Kairo."
        });

        console.log("\nKairo received a response:");
        console.log(response.text);

    } catch (error) {
        console.error("Connection failed:", error.message);
    }
}

main();
