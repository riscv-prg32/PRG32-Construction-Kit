# Tutorial 8: sound effects and music with AudioStudio

Time: about 30 minutes. You need a Blocks project (the catch game of tutorial 2 is perfect).

## 1. Open AudioStudio

Open your project and press **AudioStudio**. The **Voices** tab shows the 8 voices of the
PRG32 console. Press **Try it**: you hear voice 0. Move the **Attack** slider to the right
and try again: the note now fades in. Watch the envelope picture change.

## 2. Make a sound effect

1. Open **Sound effects** and press **New sound effect**.
2. Call it `Catch`.
3. Set **Note** to 76 and **Length** to 120 ms. Choose the sound **pulse**.
4. Set **Sustain** to 0 and **Decay** to 60: a short "blip". Press **Try it**.

## 3. Write a little tune

1. Open **Soundtracks** and press **New soundtrack**. Call it `Theme`.
2. Click the first step of voice 0 and type `C4`. Press the right arrow and type `E4`,
   then `G4`, then `C5`.
3. Put `off` after the last note so it stops.
4. Tick **Loop** and press **Play**. Press **Escape** to stop.
5. Add a bass line on voice 1 (`C3` on step 1, `G2` on step 5). Use **Mute** on voice 0 to
   hear only the bass.

AudioStudio saves by itself. The card **What the code says** shows the C lines your blocks
will become.

## 4. Use them in the game

Back in the Blocks editor, open the **Sound** category:

- put **play soundtrack Theme** in *on start*;
- put **play sound effect Catch** where the player catches something.

Press **Play** in the simulator: you hear the same sounds as in AudioStudio. Look at the
generated C: `prg32_audio_play_track(0);` and `prg32_audio_note(7, 8, 76, 255, 120);`.
Can you say what each number means? (Hint: voice, instrument, note, volume, milliseconds.)

## 5. Questions for the class

- Why does a sound effect have its own voice? What happens if the music uses that voice too?
- Change the soundtrack's tempo from 120 to 180. What changes in the generated C, and what
  does not?
- Rename the sound effect. What does the code generator say, and why does it not guess?
