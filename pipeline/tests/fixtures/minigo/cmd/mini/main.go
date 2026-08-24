package main

import (
	"fmt"
	"net/http"
	"os"

	"example.com/minigo/internal/policy"
)

func handleCheck(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintln(w, policy.Resolve(nil, r.URL.Path))
}

func handleHome(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintln(w, policy.HomeDir())
}

func main() {
	http.HandleFunc("/check", handleCheck)
	http.HandleFunc("/home", handleHome)
	mode := os.Getenv("MINIGO_MODE")
	fmt.Println("starting in", mode)
	http.ListenAndServe(":8080", nil)
}
