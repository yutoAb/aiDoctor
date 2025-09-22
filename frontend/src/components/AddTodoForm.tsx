"use client";

import { useState, FormEvent } from "react";
import { Stack, TextField, Button } from "@mui/material";
import { useSWRConfig } from "swr";

export default function AddTodoForm() {
  const [title, setTitle] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { mutate } = useSWRConfig();

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setPending(true);
    setError(null);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE}/api/todos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) throw new Error(`Create failed: ${res.status}`);

      setTitle("");

      mutate(`${process.env.NEXT_PUBLIC_API_BASE}/api/todos`);
    } catch (e: any) {
      setError(e?.message ?? "Failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <Stack direction="row" spacing={1}>
      <TextField
        id="outlined-basic"
        label="新しいToDoを入力してください"
        fullWidth
        variant="outlined"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />

      <Button variant="outlined" onClick={onSubmit}>
        {pending ? "追加中..." : "追加"}
      </Button>
      {error && <span className="text-red-500 text-sm">{error}</span>}
    </Stack>
  );
}