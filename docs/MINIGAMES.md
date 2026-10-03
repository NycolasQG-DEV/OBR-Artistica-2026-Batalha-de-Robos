# Minijogos e capturas

Esta pasta registra as interfaces dos minijogos da batalha de robôs da OBR Artística 2026. As sete imagens em [`screenshots/minigames/`](screenshots/minigames/) são capturas do renderizador Qt do próprio projeto em modo `offscreen`.

| Personagem | Minijogo | Captura | Entrada |
| --- | --- | --- | --- |
| DinoByte | Mordida Jurássica | [`mordida-jurassica.png`](screenshots/minigames/mordida-jurassica.png) | Alinhar as mãos e morder as presas. |
| DinoByte | Sucção Jurássica | [`succao-jurassica-instrucao.png`](screenshots/minigames/succao-jurassica-instrucao.png) | Virar a cabeça para sugar orbes. |
| DinoByte | Meteor Stomp | [`meteor-stomp-hud.png`](screenshots/minigames/meteor-stomp-hud.png) | Mover a cabeça entre as posições para coletar meteoros. |
| PenLinux | Dance Night | [`dance-night.png`](screenshots/minigames/dance-night.png) | Repetir as poses mostradas. |
| PenLinux | Escudo de Gelo | [`escudo-de-gelo.png`](screenshots/minigames/escudo-de-gelo.png) | Atingir os núcleos de gelo. |
| PenLinux | Notas Musicais | [`notas-musicais.png`](screenshots/minigames/notas-musicais.png) | Mover-se entre três faixas para coletar notas. |
| Defesa | Desvio | [`desvio.png`](screenshots/minigames/desvio.png) | Levar a cabeça para a zona segura. |

## Limites das imagens

- As capturas usam estados representativos gerados pelo próprio código, sem entrada de webcam e sem conexão serial. Pontuação e posição exibidas são apenas estados de prévia.
- **Sucção Jurássica:** mostra a tela de instrução. O vórtice e as orbes dependem da cena Panda3D.
- **Meteor Stomp:** mostra o HUD Qt. Os meteoros e seus efeitos dependem da cena Panda3D.
- **Desvio:** mostra a variante esquerda/direita selecionada atualmente pela lógica da batalha. O código do overlay também contém outras variantes, mas a partida ativa a variante 0.

As imagens têm 1920 × 1080 pixels. Na captura, fontes do Windows foram carregadas explicitamente porque o Qt `offscreen` não as detectou automaticamente. A captura não exigiu ESP32 nem webcam.
