document.addEventListener("input", function (e) {
  if (!e.target.classList.contains("auto-translate-input")) return;

  const input = e.target;
  const key = input.dataset.key;
  const lang = input.dataset.lang;
  const value = input.value;

  // typing state
  input.style.background = "#fff3cd";

  clearTimeout(input._timer);

  input._timer = setTimeout(() => {
    fetch("/dashboard/translations/save/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": document
          .querySelector('meta[name="csrf-token"]')
          .getAttribute("content"),
      },
      body: JSON.stringify({ key, lang, value }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.saved) {
          input.style.background = "#d1e7dd";
          setTimeout(() => (input.style.background = "white"), 500);
        } else {
          input.style.background = "#f8d7da";
          console.error(data.error);
        }
      })
      .catch(() => {
        input.style.background = "#f8d7da";
      });
  }, 500);
});
