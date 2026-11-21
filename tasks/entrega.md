# Entrega do DiskMap Studio 0.1.0

## Produto

- `diskmap/` contém o motor incremental, índice SQLite, interface PySide6, treemap Squarify, exportações e validação offline de licenças Pro.
- `site/` contém a landing SEO, captura da aplicação com dados sintéticos e os links dos três downloads. O ZIP `diskmap-studio-landing-0.1.0.zip` inclui os instaladores.
- `packaging/` e `.github/workflows/build.yml` contêm o empacotamento nativo e a emissão de licenças pelo editor.

## Evidência

- Suite local Qt offscreen com 8 testes aprovados. Implantação da licença Pro confirmada por importação e reabertura da janela em um diretório de dados temporário.
- GitHub Actions concluído com sucesso em Linux e Windows. Ubuntu obteve 8 testes aprovados. Windows obteve 7 aprovados e pulou o caso POSIX de links e FIFO. O runner Windows compilou o Inno Setup, fez instalação silenciosa e abriu o executável instalado com sucesso. [Execução 44894903972](https://github.com/franklinlem/diskmap-studio/actions/runs/44894903972)
- O pacote DEB baixado da CI abriu no Wayland local. A inspeção ELF aferiu GLIBC 2.38. O controle Debian foi corrigido e reempacotado com os mesmos binários. O empacotador agora calcula essa dependência.
- Chromium verificou a landing em 320, 375, 768, 1280 e 1920 px. O botão principal abriu a seção de downloads. Os três arquivos responderam HTTP 200 no servidor local. Hallmark executou cinco capturas, sem falhas ou regras obrigatórias pendentes. O aviso de página curta foi mantido para evitar seções redundantes.
- SHA-256 disponível para os três binários. Releases e código ficam no GitHub privado. O primeiro upload de artefatos do Actions foi barrado pela cota, então a execução final anexou os arquivos à versão em rascunho. [Versão 0.1.0 em rascunho](https://github.com/franklinlem/diskmap-studio/releases/tag/untagged-bd6373b1ecff6086de62)

## Pendências externas

- Publicar no subdomínio `diskmap.franklem.com` após autorização. A estrutura estática é compatível com hospedagem PHP/HTML na Hostinger. A consulta aos pedidos da conta via integração retornou erro.
- A execução Windows foi automatizada. Aceite visual manual em Windows e assinatura Authenticode ficam para distribuição comercial.
- O Pro funciona com licenças emitidas manualmente. Preço e checkout ficam pendentes de decisão comercial.
