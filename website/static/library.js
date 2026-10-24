// Library forms (add / edit a book or an author): check the fields in the
// browser before sending. The server checks the same rules again with the
// same messages (validate_book / validate_author / read_image in app.py).

const PRICE_PATTERN = /^\d+(\.\d{1,2})?$/;
const MAX_IMAGE_BYTES = 2 * 1024 * 1024;
const IMAGE_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"];

function checkImage(input) {
    const file = input.files && input.files[0];

    if (!file) {
        return ""; // the image is optional
    }
    if (!IMAGE_TYPES.includes(file.type)) {
        return "Choose a PNG, JPG, GIF or WEBP image";
    }
    if (file.size > MAX_IMAGE_BYTES) {
        return "The image is too large (2 MB at most)";
    }
    return "";
}

// One function per field: it returns the message, or "" when the field is fine.
const RULES = {
    book: {
        title: function (input) {
            const title = input.value.trim();
            if (title === "") return "Title is required";
            if (title.length > 200) return "Title is too long (200 characters at most)";
            return "";
        },
        price: function (input) {
            const price = input.value.trim();
            if (price === "") return "Price is required";
            if (price.startsWith("-")) return "Price cannot be negative";
            if (!PRICE_PATTERN.test(price)) return "Enter a valid price, like 120 or 99.50";
            if (Number(price) >= 100000000) return "Price is too large (99999999.99 at most)";
            return "";
        },
        author_id: function (input) {
            return input.value === "" ? "Author is required" : "";
        },
        cover: checkImage,
    },

    author: {
        name: function (input) {
            const name = input.value.trim();
            if (name === "") return "Name is required";
            if (name.length > 100) return "Name is too long (100 characters at most)";
            return "";
        },
        country: function (input) {
            const country = input.value.trim();
            if (country === "") return "Country is required";
            if (country.length > 50) return "Country is too long (50 characters at most)";
            return "";
        },
        photo: checkImage,
    },
};

// The message of a field is the element its aria-describedby points at.
function errorElementFor(input) {
    return document.getElementById(input.getAttribute("aria-describedby"));
}

function checkField(rule, input) {
    const message = rule(input);
    const errorElement = errorElementFor(input);

    errorElement.textContent = message;
    errorElement.classList.toggle("visible", message !== "");

    if (message === "") {
        input.removeAttribute("aria-invalid");
    } else {
        input.setAttribute("aria-invalid", "true");
    }

    return message === "";
}


document.querySelectorAll("form[data-validate]").forEach(function (form) {
    const rules = RULES[form.dataset.validate];
    let triedToSubmit = false;

    form.addEventListener("submit", function (event) {
        triedToSubmit = true;
        let firstInvalid = null;

        // Check ALL the fields, so every problem is shown at once.
        Object.keys(rules).forEach(function (name) {
            const input = form.elements[name];
            if (!checkField(rules[name], input) && !firstInvalid) {
                firstInvalid = input;
            }
        });

        if (firstInvalid) {
            event.preventDefault();
            firstInvalid.focus();
        }
    });

    // While typing: re-check a field after the first try, or while it shows a message.
    Object.keys(rules).forEach(function (name) {
        const input = form.elements[name];
        const eventName = input.tagName === "SELECT" || input.type === "file" ? "change" : "input";

        input.addEventListener(eventName, function () {
            if (triedToSubmit || errorElementFor(input).classList.contains("visible")) {
                checkField(rules[name], input);
            }
        });
    });
});


// Show the chosen image before it is uploaded.
document.querySelectorAll("input[type='file'][data-preview]").forEach(function (input) {
    const preview = document.getElementById(input.dataset.preview);
    const image = preview.querySelector("img");
    const originalSource = image.getAttribute("src");
    const removeBox = preview.querySelector("input[type='checkbox']");

    input.addEventListener("change", function () {
        const file = input.files && input.files[0];

        if (file && IMAGE_TYPES.includes(file.type)) {
            image.src = URL.createObjectURL(file);
            preview.hidden = false;
            if (removeBox) {
                removeBox.checked = false; // a new image replaces the old one
            }
        } else if (originalSource) {
            image.src = originalSource;
        } else {
            preview.hidden = true;
        }
    });
});
