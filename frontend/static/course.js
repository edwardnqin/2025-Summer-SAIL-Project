const API_URL = 'http://127.0.0.1:5001';
const userKey = `courses_${localStorage.getItem("wisebudUser")}`;
let courses = JSON.parse(localStorage.getItem(userKey) || "[]");

function saveCourses() {
  localStorage.setItem(userKey, JSON.stringify(courses));
}

function renderCourses() {
  const container = document.getElementById("course-list");
  container.innerHTML = "";
  courses.forEach(course => {
    const div = document.createElement("div");
    div.className = "course-card";
    div.onclick = () => window.location.href = `course_dashboard.html?course=${encodeURIComponent(course)}`;

    const span = document.createElement("span");
    span.textContent = course;

    const del = document.createElement("button");
    del.textContent = "❌";
    del.className = "delete-btn";
    del.onclick = (e) => {
      e.stopPropagation();
      courses = courses.filter(c => c !== course);
      saveCourses();
      renderCourses();
    };

    div.appendChild(span);
    div.appendChild(del);
    container.appendChild(div);
  });
}

function addCourse() {
  const input = document.getElementById("new-course");
  const val = input.value.trim();
  if (!val || courses.includes(val)) return;
  courses.push(val);
  saveCourses();
  input.value = "";
  renderCourses();
}

async function renderTodos() {
  const res = await fetch(`${API_URL}/list-todos`);
  const { todos } = await res.json();
  const list = document.getElementById("todo-list");
  list.innerHTML = "";

  todos.forEach(text => {
    const item = document.createElement("div");
    item.className = "todo-item";

    const span = document.createElement("span");
    span.textContent = text;

    const del = document.createElement("button");
    del.textContent = "❌";
    del.className = "delete-btn";
    del.onclick = async () => {
      await fetch(`${API_URL}/remove-todo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });
      renderTodos();
    };

    item.appendChild(span);
    item.appendChild(del);
    list.appendChild(item);
  });
}

async function addTodo() {
  const input = document.getElementById("new-todo");
  const val = input.value.trim();
  if (!val) return;
  await fetch(`${API_URL}/add-todo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: val })
  });
  input.value = "";
  renderTodos();
}

// INIT
renderCourses();
renderTodos();
