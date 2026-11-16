# Audio behavior

The approved profile remains: track 2 (or only available track), -50 dBFS, minimum silence 0.6 s, voice margins 0.2 s, minimum kept segment 0.65 s, H.264 CRF 16/medium/two threads and AAC 256k. A regression hash protects `perfil_probado.json` and the detector/render block.

Cuts follow the chosen track, not mixed audio. Select the microphone when gameplay is separate. Missing gameplay cannot be reconstructed. Loud non-speech may remain and quiet speech needs review: this is amplitude detection, not semantic recognition.

Boundaries follow the video frame timeline. The principal is encoded; H.264/AAC are lossy, not identical source samples. Dimensions/FPS, synchronization and cuts are checked where supported; discontinuous/variable timestamps can cause explicit limitations instead of arbitrary alignment claims.

When requested, secondary tracks follow the same kept timeline and are exported separately; a multi-track output is attempted. Sample rate/depth and decoded-sample checks protect that delivery. Unsupported lossless conversions may yield **Entrega parcial** with a verified principal still available. Read reports and track counts. Originals and earlier successful outputs are not overwritten.
