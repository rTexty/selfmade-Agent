package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"

	"github.com/joho/godotenv"
)

type Output struct {
	Answer    string        `json:"answer"`
	ToolCalls []interface{} `json:"tool_calls"`
}

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ChatRequest struct {
	Model    string    `json:"model"`
	Messages []Message `json:"messages"`
}

type ChatResponse struct {
	Choices []struct {
		Message struct {
			Content string `json:"content"`
		} `json:"message"`
	} `json:"choices"`
}

func main() {
	_ = godotenv.Load(".env.agent.secret")

	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "Usage: agent <question>")
		os.Exit(1)
	}
	question := os.Args[1]

	apiKey := os.Getenv("LLM_API_KEY")
	apiBase := strings.TrimRight(os.Getenv("LLM_API_BASE"), "/")
	model := os.Getenv("LLM_MODEL")

	if apiKey == "" || apiBase == "" || model == "" {
		fmt.Fprintln(os.Stderr, "Missing required environment variables: LLM_API_KEY, LLM_API_BASE, LLM_MODEL")
		os.Exit(1)
	}

	answer, err := callLLM(apiBase, apiKey, model, question)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error calling LLM: %v\n", err)
		os.Exit(1)
	}

	out := Output{
		Answer:    answer,
		ToolCalls: make([]interface{}, 0),
	}

	jsonOut, err := json.Marshal(out)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error formatting JSON: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(jsonOut))
}

func callLLM(apiBase, apiKey, model, prompt string) (string, error) {
	reqBody := ChatRequest{
		Model: model,
		Messages: []Message{
			{Role: "user", Content: prompt},
		},
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return "", err
	}

	endpoint := apiBase + "/chat/completions"
	req, err := http.NewRequest("POST", endpoint, bytes.NewBuffer(jsonData))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")
	if apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+apiKey)
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}

	var chatResp ChatResponse
	if err := json.NewDecoder(resp.Body).Decode(&chatResp); err != nil {
		return "", err
	}

	if len(chatResp.Choices) == 0 {
		return "", fmt.Errorf("no choices returned")
	}

	return chatResp.Choices[0].Message.Content, nil
}
