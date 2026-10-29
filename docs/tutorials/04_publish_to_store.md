# Tutorial 4: Prepare and Publish a Cartridge Bundle

Goal: create a Cartridge Store bundle from a blocks project.

## 1. Generate

Open a project and click **Generate**. Confirm that the generated C looks reasonable.

## 2. Prepare cartridge

Click **Compile**.

If the PRG32 build toolchain is installed, the result should be a publishable store bundle containing `.prg32` files. If not, the app creates a source-only teaching bundle; the Docker image has the toolchain built in (see `../install_cartridge_build.md`).

To test a single cartridge before publishing, press **Run** (the simulator on the right) or download one from the **Build** tab;
it builds one architecture and downloads that cartridge file. Publish the
bundle from **Compile** so the store gets every architecture.

## 3. Configure a store profile

1. Open **Publish**.
2. Add a profile with the Cartridge Store URL.
3. Add a bearer token if your store requires one.

## 4. Publish

1. Find the bundle in the list.
2. Click **Review**: the page shows exactly what will be sent (Store, cartridge, versions, file
   fingerprints).
3. Tick the box, click **Confirm**, and read the response panel.

Publishing needs the publisher role; without it, ask your teacher to publish for you.

A real Cartridge Store may return a pending submission that must be verified by an editor.
