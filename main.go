package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "Redirecting to Docker application...")
		
		// This is just a placeholder. The actual application runs via Docker
		// as specified in the Dockerfile.
		cmd := exec.Command("/bin/sh", "/start.sh")
		err := cmd.Start()
		if err != nil {
			log.Printf("Error starting Docker application: %v", err)
		}
	})

	log.Printf("Starting server on port %s", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
