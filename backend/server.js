// server.js
require('dotenv').config();
const express = require('express');
const cors = require('cors');
const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());

app.get('/', (req, res) => {
  res.send('Hello from your study-assistant backend!');
});

app.listen(PORT, () => {
  console.log(`Backend listening on http://localhost:${PORT}`);
});

