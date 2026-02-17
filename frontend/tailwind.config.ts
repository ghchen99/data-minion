import { type Config } from "tailwindcss";

const config: Config = {
    content: [
        "./app/**/*.{ts,tsx}",
        "./components/**/*.{ts,tsx}"
    ],
    theme: {
        extend: {
            colors: {
                minionYellow: "#FFEB3B",
                minionBlue: "#2196F3",
                minionWhite: "#FFFFFF",
            },
            fontFamily: {
                sans: ["Comic Neue", "sans-serif"],
            },
        },
    },
    plugins: [],
};

export default config;
