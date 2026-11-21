# DiskMap Studio

Analisador de armazenamento desktop, em português. A varredura lê metadados localmente e apresenta tamanhos em árvore, treemap e lista de maiores arquivos.

## Instalação

| Plataforma | Pacote |
| --- | --- |
| Windows x64 | Execute `diskmap-studio-0.1.0-windows-x64-setup.exe`. A instalação é por usuário. |
| Linux amd64 | Execute `sudo apt install ./diskmap-studio_0.1.0_amd64.deb` e abra DiskMap Studio pelo menu. |
| Linux amd64 portátil | Extraia `diskmap-studio-0.1.0-linux-amd64.tar.gz` e execute `DiskMapStudio/DiskMapStudio`. |

Os instaladores ficam em `artifacts/` na entrega local e na versão em rascunho no GitHub privado. O instalador Windows está sem assinatura Authenticode. A compilação Linux de distribuição usa Ubuntu 24.04. O pacote portátil também exige bibliotecas gráficas do sistema.

## Uso

1. Escolha **Unidades** ou **Selecionar pasta**. O rodapé mostra itens e bytes lidos. Use **Cancelar** ou **Esc** para parar após a operação de leitura em curso.
2. Navegue pela árvore com as setas. Use duplo clique em um bloco de pasta no treemap para abri-la. Arraste os divisores para redimensionar as áreas.
3. Em **Maiores arquivos**, digite parte do nome ou caminho e uma extensão exata, como `.pdf`. Use **Ctrl+F** para focar a busca ou **Ctrl+O** para escolher pasta.
4. Exporte todos os arquivos do filtro em **CSV** ou **HTML**. Escolha um nome novo. **Ocorrências** mostra o que ficou de fora. Resultados cancelados ou limitados são parciais.
5. No **Histórico Pro**, importe uma licença `.diskmap-license`. Salve varreduras concluídas. Selecione dois snapshots da mesma origem com **Ctrl** ou **Shift** e compare. A comparação mostra adições, remoções e alterações de tamanho ou data de modificação.

A edição gratuita inclui varredura, treemap, pesquisa e exportações. A edição Pro libera o histórico persistente com licença Ed25519 verificada offline. O checkout e a assinatura do instalador ficam para a publicação comercial. A emissão é local com `packaging/issue_license.py`, usando a chave privada do editor fora do repositório.

## Como a varredura funciona

- Tamanho lógico em bytes. Hard links contam por caminho e arquivos esparsos contam pelo tamanho aparente.
- Ignora links simbólicos, junções, redirecionamentos, outros dispositivos e arquivos especiais. No Linux, consulta os pontos de montagem antes da leitura, incluindo bind mounts. No POSIX, abre diretórios com descritores e sem seguir links. No Windows, revalida a sequência de diretórios por caminho.
- Conjuntos de até 2 milhões de entradas e profundidade de até 96 níveis abaixo da raiz. SQLite grava lotes no disco. A interface pagina os resultados e agrega no treemap os itens além dos 44 maiores.
- Em um volume em uso, o resultado reúne metadados observados em instantes diferentes. A comparação usa o caminho relativo e não identifica renomeações. Ocorrências de acesso ou mudanças podem afetar diferenças. Operações bloqueadas pelo sistema ou por uma unidade remota podem atrasar o cancelamento.
- A pasta da origem é lida por metadados. O aplicativo grava o índice e a licença no diretório de dados local do usuário. A exportação cria apenas um arquivo novo no destino escolhido.

## Desenvolvimento

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m diskmap
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
PYTHON_BIN=.venv/bin/python packaging/linux.sh
```

No Windows, use `.venv\Scripts\python.exe`. O workflow empacota com PyInstaller e Inno Setup, testa a instalação silenciosa e inicia o executável instalado. Para anexar pacotes, execute o workflow manualmente com a tag da versão em rascunho.

## Landing e hospedagem

`site/` contém HTML/CSS estáticos, dados estruturados, Open Graph, sitemap e uma captura real do app com arquivos sintéticos. Coloque os três instaladores em `site/downloads/` com os nomes da tabela. O destino proposto é `diskmap.franklem.com`, em um site PHP/HTML do plano Business Web Hosting da Hostinger. Publique somente o conteúdo de `site/` na raiz documental desse subdomínio após aprovação. [Gerenciador de arquivos da Hostinger](https://www.hostinger.com/support/4548688-basic-actions-in-the-file-manager-in-hostinger/)

```bash
python3 -m http.server 8000 --directory site
```
