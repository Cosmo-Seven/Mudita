document.addEventListener("input", function (e) {
  if (!e.target.classList.contains("auto-translate-input")) return;

  const input = e.target;
  const key = input.dataset.key;
  const lang = input.dataset.lang;
  const value = input.value;

  input.style.background = "#fff3cd";

  clearTimeout(input._timer);

  input._timer = setTimeout(() => {
    fetch(window.location.pathname + "save-translation/", {
      method: "POST",
      headers: {
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
          .value,
        "Content-Type": "application/json",
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
      });
  }, 500); // Auto-save after 0.5 sec pause
});
