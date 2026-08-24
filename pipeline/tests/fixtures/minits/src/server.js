// Express app: the fixture's JS route surface.
import express from "express";
import { normalize } from "./util.js";

const app = express();

function listItems(req, res) {
  res.json([normalize(" A ")]);
}

app.get("/items", listItems);
app.post("/items", (req, res) => res.status(201).end());

export default app;
