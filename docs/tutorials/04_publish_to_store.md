# Tutorial 4: Prepare and Publish a Cartridge Bundle

Goal: create a Cartridge Store bundle from a blocks project.

## 1. Generate C

Open a project and click **Generate C**. Confirm that the generated C looks reasonable.

## 2. Prepare cartridge

Click **Prepare Cartridge**.

If the PRG32 build toolchain is installed, the result should be a publishable store bundle containing `.prg32` files. If not, the app creates a source-only teaching bundle.

## 3. Configure a store profile

1. Open **Publish**.
2. Add a profile with the Cartridge Store URL.
3. Add a bearer token if your store requires one.

## 4. Publish

1. Find the bundle in the list.
2. Click **Publish**.
3. Read the response panel.

A real Cartridge Store may return a pending submission that must be verified by an editor.
