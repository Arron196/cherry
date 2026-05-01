import test from "node:test";
import assert from "node:assert/strict";

import { FIGURES, getFigureByImageName } from "../frontend_figures/manifest.mjs";

test("thesis figure manifest includes all 20 replacement targets", () => {
    assert.equal(FIGURES.length, 20);

    const imageNames = new Set(FIGURES.map((figure) => figure.imageName));
    assert.equal(imageNames.size, 20);

    assert.deepEqual(
        FIGURES.slice(0, 5).map((figure) => figure.imageName),
        ["image1.png", "image2.png", "image3.png", "image4.png", "image5.png"],
    );

    assert.equal(getFigureByImageName("image12.png")?.caption, "图5-2 哈希规范化流程图");
    assert.equal(getFigureByImageName("image20.png")?.caption, "图6-3 Canary监控与自动回滚结果图");
});

test("complex figures keep large canvas while ui and validation figures stay wide", () => {
    assert.deepEqual(getFigureByImageName("image1.png")?.size, { width: 2200, height: 1500 });
    assert.deepEqual(getFigureByImageName("image15.png")?.size, { width: 2200, height: 1480 });
    assert.deepEqual(getFigureByImageName("image17.png")?.size, { width: 1600, height: 920 });
});
