from rdkit.Chem import MolFromSmiles
from rdkit.Chem.rdDepictor import Compute2DCoords
from rdkit.Chem.Draw import MolToFile, rdMolDraw2D


def smiles_to_svg(smiles):
    molecule = MolFromSmiles(smiles)
    Compute2DCoords(molecule)
    drawer = rdMolDraw2D.MolDraw2DSVG(250, 250)
    drawer.DrawMolecule(molecule)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()
