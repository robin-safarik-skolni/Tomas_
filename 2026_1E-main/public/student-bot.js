const targetColumns = {
  I: 4,
  J: 1,
  L: 8,
  O: 5,
  S: 3,
  T: 6,
  Z: 7,
};

export function chooseCommand(snapshot) {
  if (snapshot.gameOver) {
    return null;
  }

  const targetX = targetColumns[snapshot.currentPiece.type] ?? 4;
  const pieceX = snapshot.currentPiece.x;

  if (pieceX < targetX) {
    return "right";
  }

  if (pieceX > targetX) {
    return "left";
  }

  return "drop";
}
