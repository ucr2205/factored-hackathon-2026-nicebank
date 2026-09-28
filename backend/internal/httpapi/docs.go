package httpapi

import (
	_ "embed"
	"net/http"
)

// openAPISpec documents every route in Routes(); TestOpenAPICoversAllRoutes keeps the two in sync.
//
//go:embed openapi.yaml
var openAPISpec []byte

// Swagger UI from jsDelivr, pinned. The page only reads /api/openapi.yaml; tokens typed into "Authorize" stay
// in the browser tab.
const swaggerPage = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>NiceBank API · Swagger</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css">
<style>body{margin:0}.topbar{display:none}</style></head>
<body><div id="swagger"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script>
<script>window.ui = SwaggerUIBundle({url: "/api/openapi.yaml", dom_id: "#swagger", deepLinking: true,
  persistAuthorization: false, displayRequestDuration: true, tryItOutEnabled: true});</script>
</body></html>`

func serveSpec(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/yaml; charset=utf-8")
	_, _ = w.Write(openAPISpec)
}

func serveDocs(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write([]byte(swaggerPage))
}
