# Plano do DiskMap Studio

1. Criar motor de varredura em lotes com `pathlib`, `os.scandir`, workers Qt e índice local SQLite. Ler metadados de arquivos regulares. Não seguir links ou cruzar montagens. Registrar omissões, progresso, cancelamento e limites.
2. Entregar navegação entre unidades e pastas, árvore, treemap proporcional com Qt e Squarify, maiores arquivos, busca e filtro por extensão. Usar controles redimensionáveis, foco visível, atalhos e alternativas textuais ao gráfico.
3. Persistir snapshots explícitos e comparar duas varreduras da mesma raiz por caminho relativo. Exportar os arquivos do resultado filtrado em CSV e HTML. Disponibilizar o histórico como prévia Pro offline durante o MVP.
4. Criar landing estática em português com metadados SEO e captura de um cenário sintético executado no app. Preparar a estrutura para o Business Web Hosting da Hostinger no subdomínio proposto `diskmap.franklem.com`. Publicação sujeita à autorização.
5. Verificar cenários essenciais com pytest e abrir o pacote congelado. Empacotar Debian amd64, Linux portátil e instalador nativo Windows x64 no GitHub Actions. Versionar no GitHub de Franklin com visibilidade privada inicial.

## Decisões

- A métrica é tamanho lógico em bytes. Hard links são contados por caminho e arquivos esparsos contam pelo tamanho aparente.
- A varredura usa lotes e paginação, sem carregar a árvore completa em RAM. O mapa agrega o restante dos itens após o limite visual.
- O snapshot registra metadados e o estado da varredura. A coleta em um volume ativo não equivale a uma imagem atômica do sistema de arquivos.
- Android, macOS, checkout e publicação da landing ficam fora deste MVP.
