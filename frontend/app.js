const tokenKey = "expense_tracker_token";
const usernameKey = "expense_tracker_username";

function setMessage(text, type = "success") {
  const message = document.getElementById("message");
  message.textContent = text;
  message.className = type;
}

function getToken() {
  return localStorage.getItem(tokenKey);
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${getToken()}`
  };
}

function showApp() {
  const token = getToken();
  const username = localStorage.getItem(usernameKey);

  document.getElementById("auth-section").classList.toggle("hidden", Boolean(token));
  document.getElementById("app-section").classList.toggle("hidden", !token);
  document.getElementById("logged-user").textContent = token ? `Zalogowano jako: ${username}` : "";

  if (token) {
    loadExpenses();
  }
}

async function registerUser() {
  const username = document.getElementById("register-username").value.trim();
  const password = document.getElementById("register-password").value;

  try {
    const res = await fetch("/auth/register", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Błąd rejestracji");

    setMessage("Użytkownik został zarejestrowany. Możesz się zalogować.");
  } catch (err) {
    setMessage(err.message, "error");
  }
}

async function loginUser() {
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;

  try {
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Błąd logowania");

    localStorage.setItem(tokenKey, data.token);
    localStorage.setItem(usernameKey, data.username);
    setMessage("Logowanie zakończone powodzeniem.");
    showApp();
  } catch (err) {
    setMessage(err.message, "error");
  }
}

function logoutUser() {
  localStorage.removeItem(tokenKey);
  localStorage.removeItem(usernameKey);
  setMessage("Wylogowano.");
  showApp();
}

async function createExpense() {
  const payload = {
    title: document.getElementById("expense-title").value.trim(),
    amount: document.getElementById("expense-amount").value,
    category: document.getElementById("expense-category").value.trim(),
    expense_date: document.getElementById("expense-date").value,
    description: document.getElementById("expense-description").value.trim()
  };

  try {
    const res = await fetch("/expenses", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Nie udało się dodać wydatku");

    clearExpenseForm();
    setMessage("Wydatek został dodany.");
    await loadExpenses();
  } catch (err) {
    setMessage(err.message, "error");
  }
}

function clearExpenseForm() {
  document.getElementById("expense-title").value = "";
  document.getElementById("expense-amount").value = "";
  document.getElementById("expense-category").value = "";
  document.getElementById("expense-date").value = "";
  document.getElementById("expense-description").value = "";
}

async function loadExpenses() {
  try {
    const [expensesRes, summaryRes] = await Promise.all([
      fetch("/expenses", { headers: authHeaders() }),
      fetch("/expenses/summary", { headers: authHeaders() })
    ]);

    const expenses = await expensesRes.json();
    const summary = await summaryRes.json();

    if (!expensesRes.ok) throw new Error(expenses.error || "Nie udało się pobrać wydatków");
    if (!summaryRes.ok) throw new Error(summary.error || "Nie udało się pobrać podsumowania");

    renderExpenses(expenses);
    document.getElementById("summary").textContent =
      `Liczba wydatków: ${summary.count}. Suma: ${Number(summary.total).toFixed(2)} PLN.`;
  } catch (err) {
    setMessage(err.message, "error");
  }
}

function renderExpenses(expenses) {
  const table = document.getElementById("expenses-table");
  table.innerHTML = "";

  if (!expenses.length) {
    table.innerHTML = `<tr><td colspan="6">Brak wydatków.</td></tr>`;
    return;
  }

  for (const expense of expenses) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(expense.title)}</td>
      <td>${Number(expense.amount).toFixed(2)}</td>
      <td>${escapeHtml(expense.category || "-")}</td>
      <td>${escapeHtml(expense.expense_date || "-")}</td>
      <td>${escapeHtml(expense.description || "-")}</td>
      <td>
        <button class="small secondary" onclick="editExpense(${expense.id})">Edytuj</button>
        <button class="small danger" onclick="deleteExpense(${expense.id})">Usuń</button>
      </td>
    `;
    table.appendChild(row);
  }
}

async function editExpense(id) {
  const title = prompt("Nowa nazwa wydatku:");
  if (!title) return;

  const amount = prompt("Nowa kwota:");
  if (!amount) return;

  const category = prompt("Nowa kategoria:");
  const expense_date = prompt("Nowa data w formacie RRRR-MM-DD:");
  const description = prompt("Nowy opis:");

  try {
    const res = await fetch(`/expenses/${id}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ title, amount, category, expense_date, description })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Nie udało się edytować wydatku");

    setMessage("Wydatek został zaktualizowany.");
    await loadExpenses();
  } catch (err) {
    setMessage(err.message, "error");
  }
}

async function deleteExpense(id) {
  if (!confirm("Czy na pewno usunąć ten wydatek?")) return;

  try {
    const res = await fetch(`/expenses/${id}`, {
      method: "DELETE",
      headers: authHeaders()
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Nie udało się usunąć wydatku");

    setMessage("Wydatek został usunięty.");
    await loadExpenses();
  } catch (err) {
    setMessage(err.message, "error");
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

showApp();
